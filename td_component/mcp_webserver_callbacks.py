"""
TouchDesigner MCP WebServer DAT Callbacks
==========================================
Paste this into the callbacks DAT attached to your WebServer DAT.
This is the TD-side router that receives HTTP requests from the
FastMCP server and executes operations using the TD Python API.

Setup:
  1. Create a Base COMP named 'mcp_server'
  2. Inside it, create a WebServer DAT (port 9981, Active=On)
  3. Attach this script as the callbacks DAT
  4. Optionally add a Movie File Out TOP named 'mcp_screenshot' for captures

Compatible with TouchDesigner 2025.30000+
"""

import base64
import json
import os
import re
import sys
import time
import traceback

# ─────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────

API_VERSION = "1.6.11"
SCREENSHOT_TEMP_PATH = os.path.join(os.environ.get('TEMP', os.environ.get('TMP', '/tmp')), 'td_mcp_screenshot.jpg')

# Auth + policy env is read at CALL TIME, not import time — otherwise TD's
# compiled-callback module cache pins stale values for the whole session, and
# env changes (e.g. swapping the shared secret) silently take no effect. See
# audit A-1. Module-level aliases remain below for backward compatibility with
# external callers and tests that inspect them.

def _current_shared_secret():
    """Read TD_MCP_SHARED_SECRET fresh from the environment."""
    return os.environ.get('TD_MCP_SHARED_SECRET', '').strip()


def _current_require_auth():
    """Read TD_MCP_REQUIRE_AUTH fresh from the environment.

    Auth policy:
      - If SHARED_SECRET is set: always required.
      - If TD_MCP_REQUIRE_AUTH=1 (default in production): refuse when secret is empty.
      - If TD_MCP_REQUIRE_AUTH=0: legacy permissive mode. Use only for local dev.
    """
    return os.environ.get('TD_MCP_REQUIRE_AUTH', '1').strip() not in ('0', 'false', 'no', '')


def _current_cors_origin():
    """Read TD_MCP_CORS_ORIGIN fresh from the environment.

    CORS policy:
      - Default: no CORS header (browsers are rejected by same-origin). MCP
        stdio/http clients don't need CORS.
      - TD_MCP_CORS_ORIGIN can be set to an exact origin (e.g. http://localhost:3000).
      - Wildcard '*' is NEVER used.
    """
    return os.environ.get('TD_MCP_CORS_ORIGIN', '').strip()


def _current_exec_mode():
    """Read TD_MCP_EXEC_MODE fresh from the environment."""
    mode = os.environ.get('TD_MCP_EXEC_MODE', 'restricted').strip().lower()
    if mode not in ('off', 'restricted', 'standard', 'full'):
        return 'restricted'
    return mode


# Module-level aliases (evaluated at import time) — kept so existing tests
# that do `module.SHARED_SECRET` still work. The live value used by auth
# checks comes from _current_shared_secret() etc., NOT these aliases.
SHARED_SECRET = _current_shared_secret()
REQUIRE_AUTH = _current_require_auth()
CORS_ORIGIN = _current_cors_origin()
DEFAULT_EXEC_MODE = _current_exec_mode()
RESTRICTED_IMPORT_RE = re.compile(r'(?:^|;)\s*(import|from)\s+\w+', re.MULTILINE)
RESTRICTED_TOKENS = (
    '__import__',
    'open\x28',
    'compile\x28',
    'input\x28',
    'subprocess',
    'socket',
    'requests',
    'httpx',
    'urllib',
    'pathlib',
    'shutil',
    'os.system',
    'os.popen',
    '__subclasses__',
    '__bases__',
    '__mro__',
    '__class__',
)
STANDARD_ALLOWED_IMPORTS = frozenset({
    'json', 'math', 're', 'datetime', 'collections',
    'itertools', 'functools', 'copy', 'textwrap',
    'string', 'random', 'decimal', 'fractions', 'statistics',
})
_EXEC_PAREN = 'exec' + '('
_EVAL_PAREN = 'eval' + '('
_GLOBALS_PAREN = 'globals' + '('
_LOCALS_PAREN = 'locals' + '('
STANDARD_BLOCKED_TOKENS = (
    '__import__(',
    'open(',
    'compile(',
    'input(',
    _EXEC_PAREN,
    _EVAL_PAREN,
    'subprocess',
    'socket',
    'requests',
    'httpx',
    'urllib',
    'pathlib',
    'shutil',
    'setattr',
    'delattr',
    '__subclasses__',
    '__bases__',
    '__mro__',
    'os.system',
    'os.popen',
    _GLOBALS_PAREN,
    _LOCALS_PAREN,
)
MONITOR_SUBSCRIPTIONS = {}

# ─────────────────────────────────────────────────────────────
# Main HTTP Router
# ─────────────────────────────────────────────────────────────

def onHTTPRequest(webServerDAT, request, response):
    """
    Main entry point for all MCP server requests.
    Routes to handler functions based on URI path.
    """
    uri = request.get('uri', '/')
    method = request.get('method', 'GET')

    # Parse JSON body
    body = {}
    raw_data = request.get('data', None)
    if raw_data:
        try:
            if isinstance(raw_data, bytes):
                body = json.loads(raw_data.decode('utf-8'))
            elif isinstance(raw_data, str):
                body = json.loads(raw_data)
        except (json.JSONDecodeError, UnicodeDecodeError):
            body = {}

    # CORS: apply only when a specific trusted origin is configured.
    # Never emit '*' — combined with weak auth, that lets any webpage drive TD.
    cors_origin = _current_cors_origin()
    if cors_origin:
        response['Access-Control-Allow-Origin'] = cors_origin
        response['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
        response['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, X-TD-MCP-Secret'
        response['Vary'] = 'Origin'

    # Handle OPTIONS preflight
    if method == 'OPTIONS':
        response['statusCode'] = 204
        response['statusReason'] = 'No Content'
        response['data'] = ''
        return response

    # Reject cross-site requests from browsers — MCP clients don't set Sec-Fetch-Site,
    # so this only blocks malicious webpage fetches. Same-origin/none is allowed.
    headers = _extract_headers(request)
    fetch_site = headers.get('sec-fetch-site', '')
    if fetch_site and fetch_site not in ('same-origin', 'none'):
        response['statusCode'] = 403
        response['statusReason'] = 'Forbidden'
        _send_json(response, {'error': f'cross-site fetch blocked (Sec-Fetch-Site={fetch_site})'})
        return response

    auth_error = _check_auth_error(request)
    if auth_error:
        response['statusCode'] = 401
        response['statusReason'] = 'Unauthorized'
        _send_json(response, {'error': auth_error})
        return response

    try:
        # ── Route table ──
        routes = {
            '/api/health':              handle_health,
            '/api/info':                handle_info,
            '/api/nodes':               handle_get_nodes,
            '/api/node/detail':         handle_get_node_detail,
            '/api/node/params':         handle_get_params,
            '/api/node/params/set':     handle_set_params,
            '/api/node/create':         handle_create_node,
            '/api/node/delete':         handle_delete_node,
            '/api/node/connect':        handle_connect_nodes,
            '/api/node/disconnect':     handle_disconnect_nodes,
            '/api/node/connections':    handle_get_connections,
            '/api/node/errors':         handle_get_errors,
            '/api/node/content':        handle_get_content,
            '/api/node/content/set':    handle_set_content,
            '/api/node/copy':           handle_copy_node,
            '/api/node/rename':         handle_rename_node,
            '/api/custom-parameters':   handle_custom_parameters,
            '/api/exec':                handle_exec_python,
            '/api/screenshot':          handle_screenshot,
            '/api/chop/data':           handle_chop_data,
            '/api/geometry/data':       handle_geometry_data,
            '/api/pop/inspect':         handle_pop_inspect,
            '/api/cooking':             handle_cooking_info,
            '/api/search':              handle_search_nodes,
            '/api/families':            handle_list_families,
            '/api/python/help':         handle_python_help,
            '/api/python/classes':      handle_python_classes,
            '/api/project/lifecycle':   handle_project_lifecycle,
            '/api/timeline':            handle_timeline,
            '/api/timeline/set':        handle_timeline_set,
            '/api/pulse':               handle_pulse_param,
            '/api/monitor/subscribe':   handle_monitor_subscribe,
            '/api/monitor/unsubscribe': handle_monitor_unsubscribe,
            '/api/analyze_frame':       handle_analyze_frame,
        }

        handler = routes.get(uri)
        if handler:
            result = handler(body)
        else:
            result = {'error': f'Unknown endpoint: {uri}', 'available': list(routes.keys())}
            response['statusCode'] = 404
            response['statusReason'] = 'Not Found'
            _send_json(response, result)
            return response

        response['statusCode'] = 200
        response['statusReason'] = 'OK'
        _send_json(response, result)

    except Exception as e:
        error_result = {
            'error': str(e),
            'type': type(e).__name__,
            'traceback': traceback.format_exc()
        }
        response['statusCode'] = 500
        response['statusReason'] = 'Internal Server Error'
        _send_json(response, error_result)

    return response


def _extract_headers(request):
    headers = {}
    raw = request.get('headers', {})
    if isinstance(raw, dict):
        for key, value in raw.items():
            if key is None:
                continue
            headers[str(key).strip().lower()] = str(value).strip()
    elif isinstance(raw, list):
        for item in raw:
            if isinstance(item, (tuple, list)) and len(item) == 2:
                headers[str(item[0]).strip().lower()] = str(item[1]).strip()
            elif isinstance(item, str) and ':' in item:
                key, value = item.split(':', 1)
                headers[key.strip().lower()] = value.strip()

    for key in ('authorization', 'x-td-mcp-secret'):
        if key in request and key not in headers:
            headers[key] = str(request.get(key)).strip()
    return headers


def _check_auth_error(request):
    # Read env per-request so updating TD_MCP_SHARED_SECRET or
    # TD_MCP_REQUIRE_AUTH takes effect without bouncing the callbacks module.
    # Module-level SHARED_SECRET/REQUIRE_AUTH stay as back-compat aliases only.
    secret = _current_shared_secret()
    require = _current_require_auth()

    if not secret:
        if require:
            return (
                'TD_MCP_SHARED_SECRET is not configured. Set it in the TD env or run '
                'scripts/render_mcp_config.py to generate one. To opt out for local dev, '
                'set TD_MCP_REQUIRE_AUTH=0 (not recommended).'
            )
        return None

    headers = _extract_headers(request)
    token = headers.get('x-td-mcp-secret', '')
    if not token:
        auth = headers.get('authorization', '')
        if auth.lower().startswith('bearer '):
            token = auth.split(' ', 1)[1].strip()

    if _constant_time_equals(token, secret):
        return None
    return 'Unauthorized: missing or invalid TD_MCP_SHARED_SECRET.'


def _constant_time_equals(a, b):
    """Compare two strings without early-exit timing leaks."""
    if not isinstance(a, str) or not isinstance(b, str):
        return False
    if len(a) != len(b):
        # Still do a dummy compare to avoid length-timing signal
        _ = sum(ord(x) for x in a) ^ sum(ord(y) for y in b)
        return False
    result = 0
    for x, y in zip(a, b):
        result |= ord(x) ^ ord(y)
    return result == 0


def _send_json(response, data):
    """Helper to serialize and set JSON response."""
    response['data'] = json.dumps(data, default=str).encode('utf-8')
    response['content-type'] = 'application/json'


def _serialize_op(node, include_params=False):
    """Serialize a TD operator to a dict."""
    info = {
        'name': node.name,
        'path': node.path,
        'type': node.type,
        'family': node.family,
        'label': getattr(node, 'label', ''),
        'nodeX': node.nodeX,
        'nodeY': node.nodeY,
        'isCOMP': node.isCOMP,
        'isTOP': node.isTOP,
        'isCHOP': node.isCHOP,
        'isSOP': node.isSOP,
        'isDAT': node.isDAT,
        'isMAT': node.isMAT,
        'isPOP': getattr(node, 'isPOP', False),
        'bypass': node.bypass,
        'lock': node.lock,
        'display': node.display if hasattr(node, 'display') else False,
        'render': node.render if hasattr(node, 'render') else False,
        'errors': node.errors(recurse=False) if hasattr(node, 'errors') else '',
        'warnings': node.warnings(recurse=False) if hasattr(node, 'warnings') else '',
    }
    if include_params:
        info['parameters'] = _serialize_params(node)
    return info


def _serialize_params(node):
    """Serialize all parameters of a node."""
    params = {}
    for p in node.pars():
        try:
            info = {
                'value': p.eval(),
                'default': p.default,
                'label': p.label,
                'page': p.page.name if p.page else '',
                'style': p.style,
                'min': p.min if hasattr(p, 'min') else None,
                'max': p.max if hasattr(p, 'max') else None,
                'readOnly': p.readOnly,
                'isPulse': p.isPulse,
                'isMomentary': p.isMomentary,
                'isToggle': p.isToggle,
                'isMenu': p.isMenu,
                'menuNames': list(p.menuNames) if p.isMenu else [],
                'menuLabels': list(p.menuLabels) if p.isMenu else [],
            }
            # Include expression info — this tells the AI whether a param
            # is static or driven by an expression/export
            try:
                info['expr'] = p.expr if p.expr else ''
                info['mode'] = str(p.mode)
            except Exception:
                info['expr'] = ''
                info['mode'] = 'CONSTANT'
            params[p.name] = info
        except Exception:
            params[p.name] = {'value': str(p), 'error': 'Could not fully serialize'}
    return params


# ─────────────────────────────────────────────────────────────
# Handlers
# ─────────────────────────────────────────────────────────────

def handle_health(body):
    """Health check endpoint."""
    return {
        'status': 'ok',
        'api_version': API_VERSION,
        'timestamp': time.time(),
    }


def handle_info(body):
    """Get TouchDesigner environment info."""
    return {
        'version': app.version,
        'build': app.build,
        'osName': app.osName,
        'osVersion': app.osVersion,
        'product': app.product,
        'project_name': project.name,
        'project_folder': project.folder,
        'fps': project.cookRate,
        'realTime': project.realTime,
        'frame': absTime.frame,
        'seconds': absTime.seconds,
        'timeline_start': project.cookRange[0] if hasattr(project, 'cookRange') else 1,
        'timeline_end': project.cookRange[1] if hasattr(project, 'cookRange') else 600,
        'api_version': API_VERSION,
    }


def handle_get_nodes(body):
    """List children of a path, with optional filtering."""
    path = body.get('path', '/')
    family_filter = body.get('family', None)
    type_filter = body.get('type', None)
    depth = body.get('depth', 1)
    include_params = body.get('include_params', False)
    limit = body.get('limit', 100)
    offset = body.get('offset', 0)

    target = op(path)
    if target is None:
        return {'error': f'Node not found: {path}'}

    if not target.isCOMP:
        return {'error': f'Node is not a COMP (cannot have children): {path}', 'node_type': target.type}

    children = target.children

    # Apply filters
    if family_filter:
        family_filter = family_filter.upper()
        children = [c for c in children if c.family == family_filter]
    if type_filter:
        children = [c for c in children if c.type == type_filter]

    total = len(children)
    children = children[offset:offset + limit]

    nodes = [_serialize_op(c, include_params=include_params) for c in children]

    return {
        'path': path,
        'total': total,
        'count': len(nodes),
        'offset': offset,
        'has_more': total > offset + len(nodes),
        'nodes': nodes,
    }


def handle_get_node_detail(body):
    """Get detailed info about a single node.

    Caps parameter serialization at NODE_DETAIL_PARAM_LIMIT entries (default 50)
    so a single COMP with hundreds of internal params can't blow the model
    context. Callers needing full params should use td_get_params with paging.
    """
    path = body.get('path')
    if not path:
        return {'error': 'Missing required field: path'}

    # Allow callers to override the cap via the request body, otherwise use
    # the default. Hard ceiling at 200 to keep responses bounded.
    try:
        param_limit = int(body.get('param_limit', 50))
    except (TypeError, ValueError):
        param_limit = 50
    param_limit = max(1, min(200, param_limit))

    node = op(path)
    if node is None:
        return {'error': f'Node not found: {path}'}

    detail = _serialize_op(node, include_params=False)

    # Manual capped param serialization. We deliberately don't reuse
    # _serialize_op(include_params=True) because that takes ALL params and
    # the v1.5.2 audit found a single COMP yielding ~88 KB of JSON, which
    # exceeded the model context budget on the client side.
    full_params = _serialize_params(node)
    if len(full_params) > param_limit:
        names = list(full_params.keys())[:param_limit]
        detail['parameters'] = {n: full_params[n] for n in names}
        detail['parameters_truncated'] = True
        detail['parameters_total'] = len(full_params)
        detail['parameters_returned'] = param_limit
        detail['parameters_hint'] = (
            f'Only first {param_limit}/{len(full_params)} parameters serialized to '
            'cap response size. Use td_get_params with name or page filters '
            'for the rest.'
        )
    else:
        detail['parameters'] = full_params
        detail['parameters_truncated'] = False
        detail['parameters_total'] = len(full_params)
        detail['parameters_returned'] = len(full_params)

    # Add connection info
    detail['inputs'] = []
    for conn in node.inputConnectors:
        for c in conn.connections:
            detail['inputs'].append({
                'from': c.owner.path,
                'from_index': c.index,
                'to_index': conn.index,
            })

    detail['outputs'] = []
    for conn in node.outputConnectors:
        for c in conn.connections:
            detail['outputs'].append({
                'to': c.owner.path,
                'to_index': c.index,
                'from_index': conn.index,
            })

    # Children count if COMP
    if node.isCOMP:
        detail['children_count'] = len(node.children)
        detail['child_names'] = [c.name for c in node.children[:50]]

    return detail


def handle_get_params(body):
    """Get parameters for a specific node."""
    path = body.get('path')
    if not path:
        return {'error': 'Missing required field: path'}

    node = op(path)
    if node is None:
        return {'error': f'Node not found: {path}'}

    page_filter = body.get('page', None)
    name_filter = body.get('names', None)

    params = {}
    for p in node.pars():
        if page_filter and p.page and p.page.name != page_filter:
            continue
        if name_filter and p.name not in name_filter:
            continue
        try:
            info = {
                'value': p.eval(),
                'default': p.default,
                'label': p.label,
                'page': p.page.name if p.page else '',
                'style': p.style,
                'readOnly': p.readOnly,
                'isPulse': p.isPulse,
                'isMenu': p.isMenu,
                'menuNames': list(p.menuNames) if p.isMenu else [],
            }
            # Include expression info
            try:
                info['expr'] = p.expr if p.expr else ''
                info['mode'] = str(p.mode)
            except Exception:
                info['expr'] = ''
                info['mode'] = 'CONSTANT'
            params[p.name] = info
        except Exception:
            params[p.name] = {'value': str(p), 'error': 'Could not serialize'}

    return {'path': path, 'type': node.type, 'parameters': params}


def handle_set_params(body):
    """Set one or more parameters on a node.

    Each param value can be:
      - A plain value (int, float, str, bool) → sets p.val (static constant)
      - A dict with 'expr' key → sets p.expr (Python expression that updates every frame)
        Example: {"seed": {"expr": "absTime.seconds * 10"}}
        Example: {"tx": {"expr": "op('noise1')['chan1']"}}
      - A dict with 'val' key → explicitly sets p.val (same as plain value)
      - A dict with 'reset': true → resets to default value and clears expression
      - A dict with 'mode': 'constant' → clears expression, optionally sets 'val'

    Expressions make networks REACTIVE — the parameter updates every frame.
    Without expressions, values are static snapshots.
    """
    path = body.get('path')
    params = body.get('params', {})

    if not path:
        return {'error': 'Missing required field: path'}
    if not params:
        return {'error': 'Missing required field: params'}

    node = op(path)
    if node is None:
        return {'error': f'Node not found: {path}'}

    # v1.4.6 - Bug J silent-null guard for reference-style parameters.
    # TD accepts a plain string assignment to DAT/OP/CHOP/SOP/TOP/COMP/MAT/POP/
    # POPX reference params without raising, but then resolves the value to
    # None internally and emits a node-level warning. Pre-v1.4.6 this handler
    # reported success=True with new_value=null, hiding the failure from the
    # MCP caller. The _silent_null_set check below catches that pattern and
    # flips the per-param result to success=False with the TD warning text.
    # Single-OP styles plus multi-OP list styles. The list styles caught a
    # render TOP regression in 2026-04 where camera/lights/geometry on a
    # render TOP silently resolved to None when assigned a plain string path
    # because their style is COMPS/OPS (list), not COMP/OP (single), so the
    # original singleton-only set let the silent-null slip through.
    REFERENCE_PAR_STYLES = {
        # Single-OP reference styles.
        'DAT', 'OP', 'CHOP', 'SOP', 'TOP', 'COMP', 'MAT', 'POP', 'POPX',
        # Multi-OP list reference styles (TD uses the plural form for
        # render TOP camera/lights/geometry, attribute COMP COMPs, etc.).
        'DATS', 'OPS', 'CHOPS', 'SOPS', 'TOPS', 'COMPS', 'MATS', 'POPS', 'POPXS',
        # OPLIST shows up in some TD builds for the same role.
        'OPLIST',
    }

    def _is_silent_null(par, requested_value, resolved_value):
        """Return True iff the set succeeded syntactically but TD resolved to
        None because the param needs an OP reference (or expression), not a
        plain string. Numeric zeros, empty strings on Str params, and False
        on Toggles all resolve to non-None, so this specifically targets
        None + reference-style + non-empty str."""
        if resolved_value is not None:
            return False
        if not isinstance(requested_value, str):
            return False
        if not requested_value.strip():
            return False
        try:
            style = getattr(par, 'style', '')
        except Exception:
            style = ''
        return style in REFERENCE_PAR_STYLES

    def _build_silent_null_result(par_name, par, requested_value, node_for_warnings):
        """Shape the success=False payload when _is_silent_null trips."""
        try:
            warn_text = (node_for_warnings.warnings() or '').strip()
        except Exception:
            warn_text = ''
        try:
            style = getattr(par, 'style', '')
        except Exception:
            style = ''
        err = (
            'Parameter {0!r} is a reference-style param (style={1}) and '
            "needs an actual OP reference, not a plain string. The value "
            "{2!r} did not resolve - TD assigned null."
        ).format(par_name, style or 'unknown', requested_value)
        # Only cite the TD warning if it looks related to this set.
        if warn_text and (
            'Invalid path' in warn_text
            or 'not found' in warn_text.lower()
            or par_name in warn_text
        ):
            err += ' TD warning: ' + warn_text
        return {
            'success': False,
            'mode': 'constant',
            'error': err,
            'style': style,
            'new_value': None,
        }

    results = {}
    for name, value in params.items():
        try:
            p = getattr(node.par, name, None)
            if p is None:
                results[name] = {'success': False, 'error': f'Parameter not found: {name}'}
                continue
            if p.readOnly:
                results[name] = {'success': False, 'error': f'Parameter is read-only: {name}'}
                continue

            # Expression mode: {"param": {"expr": "absTime.seconds * 10"}}
            if isinstance(value, dict) and 'expr' in value:
                p.expr = value['expr']
                results[name] = {
                    'success': True,
                    'mode': 'expression',
                    'expr': value['expr'],
                    'current_value': p.eval(),
                }
            # Reset to default: {"param": {"reset": true}}
            elif isinstance(value, dict) and value.get('reset'):
                p.val = p.default
                p.expr = ''
                results[name] = {'success': True, 'mode': 'reset', 'new_value': p.eval()}
            # Clear expression, force constant: {"param": {"mode": "constant", "val": 42}}
            elif isinstance(value, dict) and value.get('mode') == 'constant':
                p.expr = ''
                if 'val' in value:
                    p.val = value['val']
                    resolved = p.eval()
                    if _is_silent_null(p, value['val'], resolved):
                        results[name] = _build_silent_null_result(name, p, value['val'], node)
                        continue
                results[name] = {'success': True, 'mode': 'constant', 'new_value': p.eval()}
            # Explicit val mode: {"param": {"val": 42}}
            elif isinstance(value, dict) and 'val' in value:
                p.val = value['val']
                resolved = p.eval()
                if _is_silent_null(p, value['val'], resolved):
                    results[name] = _build_silent_null_result(name, p, value['val'], node)
                    continue
                results[name] = {'success': True, 'mode': 'constant', 'new_value': resolved}
            # Plain value (backwards compatible)
            else:
                p.val = value
                resolved = p.eval()
                if _is_silent_null(p, value, resolved):
                    results[name] = _build_silent_null_result(name, p, value, node)
                    continue
                results[name] = {'success': True, 'mode': 'constant', 'new_value': resolved}
        except Exception as e:
            results[name] = {'success': False, 'error': str(e)}

    return {'path': path, 'results': results}


def handle_create_node(body):
    """Create a new node with optional positioning."""
    parent_path = body.get('parent_path', '/')
    node_type = body.get('node_type')
    name = body.get('name', None)
    node_x = body.get('nodeX', None)
    node_y = body.get('nodeY', None)

    if not node_type:
        return {'error': 'Missing required field: node_type'}

    parent_node = op(parent_path)
    if parent_node is None:
        return {'error': f'Parent node not found: {parent_path}'}

    if not parent_node.isCOMP:
        return {'error': f'Parent is not a COMP: {parent_path}'}

    try:
        new_node = parent_node.create(node_type, name)

        # Set position if provided — keeps networks readable
        if node_x is not None:
            new_node.nodeX = int(node_x)
        if node_y is not None:
            new_node.nodeY = int(node_y)

        return {
            'success': True,
            'node': _serialize_op(new_node),
        }
    except Exception as e:
        return {'error': f'Failed to create node: {str(e)}', 'node_type': node_type}


def handle_delete_node(body):
    """Delete a node by path."""
    path = body.get('path')
    if not path:
        return {'error': 'Missing required field: path'}

    node = op(path)
    if node is None:
        return {'error': f'Node not found: {path}'}

    node_info = {'name': node.name, 'path': node.path, 'type': node.type}

    try:
        node.destroy()
        return {'success': True, 'deleted': node_info}
    except Exception as e:
        return {'error': f'Failed to delete node: {str(e)}'}


def handle_connect_nodes(body):
    """Connect output of one node to input of another."""
    source_path = body.get('source_path')
    target_path = body.get('target_path')
    source_index = body.get('source_index', 0)
    target_index = body.get('target_index', 0)

    if not source_path or not target_path:
        return {'error': 'Missing required fields: source_path and target_path'}

    source = op(source_path)
    target = op(target_path)

    if source is None:
        return {'error': f'Source node not found: {source_path}'}
    if target is None:
        return {'error': f'Target node not found: {target_path}'}

    # Validate connector indices before access
    num_outputs = len(source.outputConnectors)
    num_inputs = len(target.inputConnectors)
    if source_index >= num_outputs:
        return {'error': f'source_index {source_index} out of range — {source.path} has {num_outputs} output(s) (0–{num_outputs - 1})'}
    if target_index >= num_inputs:
        return {'error': f'target_index {target_index} out of range — {target.path} has {num_inputs} input(s) (0–{num_inputs - 1})'}

    try:
        source.outputConnectors[source_index].connect(target.inputConnectors[target_index])
        return {
            'success': True,
            'connection': {
                'source': source.path,
                'source_index': source_index,
                'target': target.path,
                'target_index': target_index,
            }
        }
    except Exception as e:
        return {'error': f'Failed to connect: {str(e)}'}


def handle_disconnect_nodes(body):
    """Disconnect a node's input or output."""
    path = body.get('path')
    connector_type = body.get('connector_type', 'input')  # 'input' or 'output'
    index = body.get('index', 0)

    if not path:
        return {'error': 'Missing required field: path'}

    node = op(path)
    if node is None:
        return {'error': f'Node not found: {path}'}

    # Validate connector index
    if connector_type == 'input':
        num_connectors = len(node.inputConnectors)
    else:
        num_connectors = len(node.outputConnectors)
    if index >= num_connectors:
        return {'error': f'{connector_type} index {index} out of range — {path} has {num_connectors} {connector_type}(s) (0–{num_connectors - 1})'}

    try:
        if connector_type == 'input':
            node.inputConnectors[index].disconnect()
        else:
            node.outputConnectors[index].disconnect()
        return {'success': True, 'path': path, 'connector_type': connector_type, 'index': index}
    except Exception as e:
        return {'error': f'Failed to disconnect: {str(e)}'}


def handle_get_connections(body):
    """Get all connections for a node."""
    path = body.get('path')
    if not path:
        return {'error': 'Missing required field: path'}

    node = op(path)
    if node is None:
        return {'error': f'Node not found: {path}'}

    inputs = []
    for conn in node.inputConnectors:
        for c in conn.connections:
            inputs.append({
                'from_path': c.owner.path,
                'from_index': c.index,
                'to_index': conn.index,
            })

    outputs = []
    for conn in node.outputConnectors:
        for c in conn.connections:
            outputs.append({
                'to_path': c.owner.path,
                'to_index': c.index,
                'from_index': conn.index,
            })

    return {'path': path, 'inputs': inputs, 'outputs': outputs}


def handle_get_errors(body):
    """Get errors/warnings for a node, optionally recursive with depth limit."""
    path = body.get('path', '/')
    recurse = body.get('recurse', True)
    max_depth = body.get('max_depth', 10)  # prevent runaway on huge projects

    node = op(path)
    if node is None:
        return {'error': f'Node not found: {path}'}

    results = []
    truncated = False

    def collect_errors(n, depth=0):
        nonlocal truncated
        errs = n.errors(recurse=False) if hasattr(n, 'errors') else ''
        warns = n.warnings(recurse=False) if hasattr(n, 'warnings') else ''
        if errs or warns:
            results.append({
                'path': n.path,
                'name': n.name,
                'type': n.type,
                'errors': errs,
                'warnings': warns,
            })
        if recurse and n.isCOMP and depth < max_depth:
            for child in n.children:
                collect_errors(child, depth + 1)
        elif recurse and n.isCOMP and depth >= max_depth:
            truncated = True

    collect_errors(node)
    result = {'path': path, 'recurse': recurse, 'count': len(results), 'issues': results}
    if truncated:
        result['warning'] = f'Search truncated at depth {max_depth}. Use max_depth to go deeper.'
    return result


def handle_get_content(body):
    """Get text/table content from a DAT."""
    path = body.get('path')
    if not path:
        return {'error': 'Missing required field: path'}

    node = op(path)
    if node is None:
        return {'error': f'Node not found: {path}'}

    if not node.isDAT:
        return {'error': f'Node is not a DAT: {path} (type: {node.type})'}

    # Prefer the DAT's own isTable flag over heuristic numRows check.
    # textDAT.numRows is 1 (the full text counted as one row) which previously
    # caused textDAT to be returned as a 1x1 table — unintuitive for callers
    # expecting plain text back from a text DAT.
    is_table = bool(getattr(node, 'isTable', False))
    try:
        if is_table:
            rows = []
            for r in range(node.numRows):
                row = []
                for c in range(node.numCols):
                    row.append(node[r, c].val)
                rows.append(row)
            return {
                'path': path,
                'format': 'table',
                'numRows': node.numRows,
                'numCols': node.numCols,
                'data': rows,
            }
        return {
            'path': path,
            'format': 'text',
            'text': node.text if hasattr(node, 'text') else '',
        }
    except Exception as e:
        return {
            'path': path,
            'format': 'text',
            'text': node.text if hasattr(node, 'text') else '',
            'warning': f'Content read failed, fell back to text: {str(e)}',
        }


def handle_set_content(body):
    """Set text/table content on a DAT."""
    path = body.get('path')
    text = body.get('text', None)
    table = body.get('table', None)

    if not path:
        return {'error': 'Missing required field: path'}

    node = op(path)
    if node is None:
        return {'error': f'Node not found: {path}'}

    if not node.isDAT:
        return {'error': f'Node is not a DAT: {path}'}

    try:
        if text is not None:
            node.text = text
            return {'success': True, 'path': path, 'format': 'text', 'length': len(text)}
        elif table is not None:
            node.clear()
            wrote = False
            # Preferred path for Table DATs.
            if hasattr(node, 'appendRow'):
                try:
                    for row in table:
                        node.appendRow([str(v) for v in row])
                    wrote = True
                except Exception:
                    node.clear()

            # Fallback path for DATs that expose indexed assignment only.
            if not wrote:
                if hasattr(node, 'setSize'):
                    try:
                        rows = len(table)
                        cols = max((len(row) for row in table), default=0)
                        node.setSize(rows, cols)
                    except Exception:
                        pass
                for r, row in enumerate(table):
                    for c, val in enumerate(row):
                        node[r, c] = val
            return {'success': True, 'path': path, 'format': 'table', 'rows': len(table)}
        else:
            return {'error': 'Provide either "text" or "table" field'}
    except Exception as e:
        return {'error': f'Failed to set content: {str(e)}'}


def handle_copy_node(body):
    """Copy/duplicate a node."""
    source_path = body.get('source_path')
    dest_parent = body.get('dest_parent', None)
    new_name = body.get('new_name', None)
    node_x = body.get('nodeX', None)
    node_y = body.get('nodeY', None)

    if not source_path:
        return {'error': 'Missing required field: source_path'}

    source = op(source_path)
    if source is None:
        return {'error': f'Source node not found: {source_path}'}

    parent = op(dest_parent) if dest_parent else source.parent()
    if parent is None:
        return {'error': f'Destination parent not found: {dest_parent}'}

    try:
        new_node = parent.copy(source, name=new_name)
        # TD's parent.copy() places the new node at the source's position which
        # causes overlap. If the caller supplied explicit coordinates, honor
        # them; otherwise offset by +150 X to keep the copy visible.
        try:
            if node_x is not None:
                new_node.nodeX = int(node_x)
            else:
                new_node.nodeX = int(getattr(source, 'nodeX', 0)) + 150
            if node_y is not None:
                new_node.nodeY = int(node_y)
            else:
                new_node.nodeY = int(getattr(source, 'nodeY', 0))
        except Exception:
            # Node position is cosmetic; don't fail the copy if it can't be set.
            pass
        return {'success': True, 'node': _serialize_op(new_node)}
    except Exception as e:
        return {'error': f'Failed to copy node: {str(e)}'}


def handle_rename_node(body):
    """Rename a node."""
    path = body.get('path')
    new_name = body.get('new_name')

    if not path or not new_name:
        return {'error': 'Missing required fields: path and new_name'}

    node = op(path)
    if node is None:
        return {'error': f'Node not found: {path}'}

    old_name = node.name
    try:
        node.name = new_name
        return {'success': True, 'old_name': old_name, 'new_name': node.name, 'new_path': node.path}
    except Exception as e:
        return {'error': f'Failed to rename: {str(e)}'}


def handle_custom_parameters(body):
    """Create or update custom parameter pages and parameters on a COMP."""
    path = body.get('path')
    page_name = body.get('page')
    param_specs = body.get('params', [])

    if not path or not page_name:
        return {'error': 'Missing required fields: path and page'}
    if not isinstance(param_specs, list) or not param_specs:
        return {'error': 'Missing required field: params'}

    node = op(path)
    if node is None:
        return {'error': f'Node not found: {path}'}
    if not getattr(node, 'isCOMP', False):
        return {'error': f'Node is not a COMP: {path}'}

    try:
        page, page_created = _find_custom_page(node, page_name)
        created = []
        for spec in param_specs:
            if not isinstance(spec, dict):
                return {'error': 'Each param specification must be an object'}
            created.append(_create_custom_parameter(page, spec))
        return {
            'success': True,
            'path': path,
            'page': page_name,
            'page_created': page_created,
            'count': len(created),
            'parameters': created,
        }
    except Exception as exc:
        return {'error': f'Failed to create custom parameters: {str(exc)}'}


def _normalize_for_check(code):
    """Lowercase and collapse whitespace before '(' to defeat bypass via 'open (' etc."""
    return re.sub(r'\s+\(', '(', code.lower())


def _restricted_exec_violation(code):
    if RESTRICTED_IMPORT_RE.search(code):
        return 'restricted mode blocks import statements'
    normalized = _normalize_for_check(code)
    for token in RESTRICTED_TOKENS:
        if token in normalized:
            return f'restricted mode blocks token: {token}'
    # TD-side sandbox escape: `op(...).create(textDAT)` then write `.text` lets
    # a caller stash arbitrary Python in a DAT and then execute it via
    # `mod.<dat>.func()`. Block the pieces of that pattern in restricted mode.
    # Users who genuinely need DAT authoring should run in standard or full.
    dat_escape_tokens = (
        'create(textdat',
        'create(textDAT'.lower(),
        '.text=',
        '.text =',
        '.par.file=',
        '.par.file =',
    )
    for token in dat_escape_tokens:
        if token in normalized:
            return f'restricted mode blocks DAT-exec pattern: {token}'
    return None


def _standard_exec_violation(code):
    normalized = _normalize_for_check(code)
    for token in STANDARD_BLOCKED_TOKENS:
        if token in normalized:
            return f'standard mode blocks token: {token}'

    for match in RESTRICTED_IMPORT_RE.finditer(code):
        line = match.group(0).strip()
        parts = line.split()
        if parts[0] == 'from':
            mod_name = parts[1]
        else:
            mod_name = parts[1]
        top_level = mod_name.split('.')[0]
        if top_level not in STANDARD_ALLOWED_IMPORTS:
            return f'standard mode blocks import of: {top_level}'

    return None


def _build_exec_globals(exec_mode):
    import importlib as _importlib
    context = {
        'op': op,
        'ops': ops,
        'project': project,
        'app': app,
        'absTime': absTime,
        'me': me,
        'parent': parent,
        'mod': mod,
        'ui': ui,
        'tdu': tdu,
    }
    # Builtins safe for both standard and restricted modes — no exec/eval/open/import/__subclasses__
    safe_builtins = {
        'abs': abs,
        'all': all,
        'any': any,
        'bool': bool,
        'dict': dict,
        'enumerate': enumerate,
        'float': float,
        'getattr': getattr,
        'hasattr': hasattr,
        'isinstance': isinstance,
        'issubclass': issubclass,
        'int': int,
        'len': len,
        'list': list,
        'map': map,
        'filter': filter,
        'max': max,
        'min': min,
        'pow': pow,
        'print': print,
        'range': range,
        'repr': repr,
        'reversed': reversed,
        'round': round,
        'set': set,
        'sorted': sorted,
        'str': str,
        'sum': sum,
        'tuple': tuple,
        'type': type,
        'zip': zip,
    }
    if exec_mode == 'standard':
        for _mod_name in STANDARD_ALLOWED_IMPORTS:
            try:
                context[_mod_name] = _importlib.import_module(_mod_name)
            except ImportError:
                pass
        context['__builtins__'] = safe_builtins
        return context
    if exec_mode != 'restricted':
        return context

    # Restricted mode — even fewer builtins (no getattr/hasattr/type/isinstance)
    restricted_builtins = {k: v for k, v in safe_builtins.items()
                           if k not in ('getattr', 'hasattr', 'isinstance', 'issubclass', 'type', 'map', 'filter', 'repr')}
    safe = {'__builtins__': restricted_builtins}
    safe.update(context)
    return safe


def _json_safe_value(value, depth=0, max_items=128):
    """Best-effort conversion of TouchDesigner/Python values to JSON-safe payloads."""
    if depth > 4:
        return str(value)

    if value is None or isinstance(value, (bool, int, float, str)):
        return value

    if isinstance(value, bytes):
        return base64.b64encode(value).decode('ascii')

    if isinstance(value, dict):
        result = {}
        for i, (key, item) in enumerate(value.items()):
            if i >= max_items:
                result['__truncated__'] = True
                break
            result[str(key)] = _json_safe_value(item, depth + 1, max_items=max_items)
        return result

    if isinstance(value, (list, tuple, set)):
        result = []
        for i, item in enumerate(value):
            if i >= max_items:
                result.append({'__truncated__': True})
                break
            result.append(_json_safe_value(item, depth + 1, max_items=max_items))
        return result

    if hasattr(value, 'path') and hasattr(value, 'name'):
        return {
            'path': str(getattr(value, 'path', '')),
            'name': str(getattr(value, 'name', '')),
            'type': str(getattr(value, 'type', value.__class__.__name__)),
        }

    if all(hasattr(value, attr) for attr in ('x', 'y')):
        coords = [float(value.x), float(value.y)]
        if hasattr(value, 'z'):
            coords.append(float(value.z))
        return coords

    return str(value)


def _serialize_exec_result(value):
    structured_types = (type(None), bool, int, float, str, dict, list, tuple, set)
    return {
        'result': _json_safe_value(value),
        'result_type': type(value).__name__ if value is not None else 'NoneType',
        'result_is_structured': isinstance(value, structured_types),
    }


def _safe_td_call(target, attr_name, *args, **kwargs):
    attr = getattr(target, attr_name, None)
    if attr is None:
        return None
    if not callable(attr):
        return attr
    try:
        return attr(*args, **kwargs)
    except TypeError:
        try:
            return attr(*args)
        except Exception:
            return None
    except Exception:
        return None


def _parse_attribute_descriptor(item):
    text = str(item)
    match = re.match(r"^([^:]+):\s*(\d+)\s*<class '([^']+)'>$", text)
    if match:
        return {
            'name': match.group(1),
            'size': int(match.group(2)),
            'type': match.group(3),
            'raw': text,
        }
    return {'name': text, 'raw': text}


def _collect_attribute_descriptors(collection):
    descriptors = []
    try:
        for item in collection:
            descriptors.append(_parse_attribute_descriptor(item))
    except Exception:
        pass
    return descriptors


def _attribute_names(descriptors):
    names = []
    for item in descriptors:
        name = item.get('name')
        if isinstance(name, str) and name:
            names.append(name)
    return names


def _serialize_bounds(bounds):
    if bounds is None:
        return None

    def _vec(obj):
        if obj is None:
            return None
        result = []
        for attr in ('x', 'y', 'z'):
            if hasattr(obj, attr):
                result.append(float(getattr(obj, attr)))
        return result or None

    return {
        'min': _vec(getattr(bounds, 'min', None)),
        'max': _vec(getattr(bounds, 'max', None)),
        'center': _vec(getattr(bounds, 'center', None)),
        'size': _vec(getattr(bounds, 'size', None)),
    }


def _sample_pop_attribute(node, method_name, attr_name, start, count, delayed):
    method = getattr(node, method_name, None)
    if not callable(method):
        return {'error': f'{method_name} unavailable'}
    try:
        values = method(attr_name, startIndex=start, count=count, delayed=delayed)
    except TypeError:
        try:
            values = method(attr_name, start, count, delayed)
        except Exception as exc:
            return {'error': str(exc)}
    except Exception as exc:
        return {'error': str(exc)}

    return {
        'attribute': attr_name,
        'start': start,
        'count': count,
        'values': _json_safe_value(values),
    }


def _pick_default_pop_samples(available_names):
    preferred = ['P', 'PartVel', 'PartAge', 'PartLifeSpan', 'Noise', 'PartForce', 'PartId']
    result = []
    for name in preferred:
        if name in available_names:
            result.append(name)
        if len(result) >= 4:
            break
    return result


def _group_members(group):
    if group is None:
        return []
    if isinstance(group, (list, tuple)):
        return list(group)
    try:
        members = list(group)
        if members:
            return members
    except Exception:
        pass
    return [group]


def _broadcast_values(value, count):
    if count <= 0:
        return []
    if isinstance(value, (list, tuple)):
        values = list(value)
        if not values:
            return [None] * count
        if len(values) >= count:
            return values[:count]
        return values + [values[-1]] * (count - len(values))
    return [value] * count


def _set_attr_if_supported(target, attr_name, value):
    if value is None or target is None:
        return
    try:
        setattr(target, attr_name, value)
    except Exception:
        pass


def _assign_custom_group_defaults(group, spec):
    members = _group_members(group)
    if not members:
        return

    if spec.get('menu_names'):
        menu_names = list(spec.get('menu_names') or [])
        menu_labels = list(spec.get('menu_labels') or menu_names)
        for target in [group] + members[:1]:
            _set_attr_if_supported(target, 'menuNames', menu_names)
            _set_attr_if_supported(target, 'menuLabels', menu_labels)

    for attr_name in ('min', 'max', 'norm_min', 'norm_max', 'clamp_min', 'clamp_max'):
        source_value = spec.get(attr_name)
        target_attr = {
            'norm_min': 'normMin',
            'norm_max': 'normMax',
            'clamp_min': 'clampMin',
            'clamp_max': 'clampMax',
        }.get(attr_name, attr_name)
        for member in members:
            _set_attr_if_supported(member, target_attr, source_value)

    if spec.get('default', None) is None:
        return

    for member, value in zip(members, _broadcast_values(spec.get('default'), len(members))):
        _set_attr_if_supported(member, 'default', value)
        _set_attr_if_supported(member, 'val', value)


def _find_custom_page(node, page_name):
    for collection_name in ('customPages', 'pages'):
        pages = getattr(node, collection_name, None)
        if pages is None:
            continue
        try:
            for page in pages:
                if str(getattr(page, 'name', '')) == page_name:
                    return page, False
        except Exception:
            continue
    return node.appendCustomPage(page_name), True


def _create_custom_parameter(page, spec):
    kind = str(spec.get('kind', '')).lower()
    method_name = {
        'float': 'appendFloat',
        'int': 'appendInt',
        'toggle': 'appendToggle',
        'menu': 'appendMenu',
        'str': 'appendStr',
        'string': 'appendStr',
        'rgb': 'appendRGB',
        'rgba': 'appendRGBA',
        'pulse': 'appendPulse',
        'file': 'appendFile',
        'filesave': 'appendFileSave',
        'folder': 'appendFolder',
        'chop': 'appendCHOP',
        'comp': 'appendCOMP',
        'dat': 'appendDAT',
        'mat': 'appendMAT',
        'header': 'appendHeader',
    }.get(kind)
    if not method_name:
        raise ValueError(f"Unsupported custom parameter kind: {kind}")

    method = getattr(page, method_name, None)
    if not callable(method):
        raise ValueError(f"Page does not support method {method_name}")

    kwargs = {
        'label': spec.get('label'),
        'order': spec.get('order'),
        'replace': bool(spec.get('replace', True)),
    }
    kwargs = {key: value for key, value in kwargs.items() if value is not None}
    if kind in ('float', 'int'):
        kwargs['size'] = int(spec.get('size', 1) or 1)

    group = method(spec.get('name'), **kwargs)
    _assign_custom_group_defaults(group, spec)
    members = _group_members(group)
    return {
        'kind': kind,
        'name': spec.get('name'),
        'label': spec.get('label') or spec.get('name'),
        'member_count': len(members),
        'members': [str(getattr(member, 'name', member)) for member in members],
    }


def handle_exec_python(body):
    """Execute arbitrary Python code inside TouchDesigner.

    Supports an optional timeout_ms parameter (default 10000) to prevent
    runaway code from freezing TD.  Uses a threading.Timer to interrupt
    execution via a KeyboardInterrupt if it exceeds the limit.
    """
    code = body.get('code')
    if not code:
        return {'error': 'Missing required field: code'}

    _MODE_RANK = {'off': 0, 'restricted': 1, 'standard': 2, 'full': 3}
    default_mode = _current_exec_mode()  # read env per-request; see A-1
    exec_mode = str(body.get('exec_mode', default_mode)).strip().lower()
    if exec_mode not in _MODE_RANK:
        exec_mode = default_mode
    # Cap requested mode at server-configured default — clients cannot escalate
    if _MODE_RANK.get(exec_mode, 0) > _MODE_RANK.get(default_mode, 0):
        exec_mode = default_mode

    if exec_mode == 'off':
        return {
            'error': 'Python execution is disabled by TD_MCP_EXEC_MODE=off',
            'type': 'PermissionError',
            'exec_mode': exec_mode,
        }

    if exec_mode == 'restricted':
        violation = _restricted_exec_violation(code)
        if violation:
            return {
                'error': violation,
                'type': 'PermissionError',
                'exec_mode': exec_mode,
            }

    if exec_mode == 'standard':
        violation = _standard_exec_violation(code)
        if violation:
            return {
                'error': violation,
                'type': 'PermissionError',
                'exec_mode': exec_mode,
            }

    timeout_ms = body.get('timeout_ms', 10000)
    timeout_sec = max(1, min(timeout_ms / 1000, 30))  # clamp 1–30s

    # Capture stdout
    import ctypes
    import io
    import threading
    old_stdout = sys.stdout
    old_stderr = sys.stderr
    captured_out = io.StringIO()
    captured_err = io.StringIO()
    timed_out = [False]

    def _timeout_handler():
        """Interrupt the main thread if execution takes too long."""
        timed_out[0] = True
        # Raise KeyboardInterrupt in the main thread
        try:
            ctypes.pythonapi.PyThreadState_SetAsyncExc(
                ctypes.c_ulong(threading.main_thread().ident),
                ctypes.py_object(KeyboardInterrupt)
            )
        except Exception:
            pass  # best-effort timeout

    timer = threading.Timer(timeout_sec, _timeout_handler)
    result_value = None
    try:
        sys.stdout = captured_out
        sys.stderr = captured_err
        timer.start()
        exec_globals = _build_exec_globals(exec_mode)

        # Try exec first, fall back to eval for expressions
        try:
            exec(code, exec_globals)
            # Check if there's a __result__ variable
            result_value = exec_globals.get('__result__', None)
        except SyntaxError:
            # Might be a simple expression
            result_value = eval(code, exec_globals)
    except KeyboardInterrupt:
        sys.stdout = old_stdout
        sys.stderr = old_stderr
        timer.cancel()
        return {
            'error': f'Execution timed out after {timeout_sec}s. Avoid infinite loops or blocking operations.',
            'type': 'TimeoutError',
            'exec_mode': exec_mode,
            'stdout': captured_out.getvalue(),
            'stderr': captured_err.getvalue(),
        }
    except Exception as e:
        sys.stdout = old_stdout
        sys.stderr = old_stderr
        timer.cancel()
        return {
            'error': str(e),
            'type': type(e).__name__,
            'exec_mode': exec_mode,
            'traceback': traceback.format_exc(),
            'stdout': captured_out.getvalue(),
            'stderr': captured_err.getvalue(),
        }
    finally:
        timer.cancel()
        sys.stdout = old_stdout
        sys.stderr = old_stderr

    payload = {
        'success': True,
        'exec_mode': exec_mode,
        'stdout': captured_out.getvalue(),
        'stderr': captured_err.getvalue(),
    }
    payload.update(_serialize_exec_result(result_value))
    return payload


def handle_screenshot(body):
    """Capture a TOP as a JPEG image and return base64.

    Uses JPEG with configurable quality (0.0–1.0 scale, TD 2025+) to keep
    captures well under the 1 MB MCP response-size limit after base64 encoding.
    """
    path = body.get('path', None)
    quality = float(body.get('quality', 0.5))  # TD 2025 uses 0.0–1.0 scale

    try:
        if path:
            target = op(path)
            if target is None:
                return {'error': f'Node not found: {path}'}
            if not target.isTOP:
                return {'error': f'Node is not a TOP: {path} (type: {target.type})'}
        else:
            return {'error': 'Provide path to a TOP node to screenshot'}

        # Use saveByteArray for in-memory JPEG capture
        img_bytes = target.saveByteArray('.jpg', quality=quality)
        img_b64 = base64.b64encode(bytes(img_bytes)).decode('ascii')

        return {
            'success': True,
            'path': target.path,
            'width': target.width,
            'height': target.height,
            'format': 'jpeg',
            'data_base64': img_b64,
            'size_bytes': len(img_bytes),
        }
    except Exception as e:
        # Fallback: try file-based save
        try:
            target.save(SCREENSHOT_TEMP_PATH, quality=quality)
            with open(SCREENSHOT_TEMP_PATH, 'rb') as f:
                img_bytes = f.read()
            img_b64 = base64.b64encode(img_bytes).decode('ascii')
            return {
                'success': True,
                'path': target.path,
                'format': 'jpeg',
                'data_base64': img_b64,
                'size_bytes': len(img_bytes),
                'method': 'file_fallback',
            }
        except Exception as e2:
            return {'error': f'Screenshot failed: {str(e)} / fallback: {str(e2)}'}


def handle_chop_data(body):
    """Read channel data from a CHOP."""
    path = body.get('path')
    channel_names = body.get('channels', None)  # list of names, or None for all
    sample_range = body.get('range', None)  # [start, end] or None for all

    if not path:
        return {'error': 'Missing required field: path'}

    node = op(path)
    if node is None:
        return {'error': f'Node not found: {path}'}

    if not node.isCHOP:
        return {'error': f'Node is not a CHOP: {path}'}

    result = {
        'path': path,
        'numChans': node.numChans,
        'numSamples': node.numSamples,
        'rate': node.rate,
        'channels': {},
    }

    for chan in node.chans():
        if channel_names and chan.name not in channel_names:
            continue

        samples = list(chan.vals)
        if sample_range:
            start = max(0, sample_range[0])
            end = min(len(samples), sample_range[1])
            samples = samples[start:end]

        # Limit to 1000 samples max to avoid huge responses
        if len(samples) > 1000:
            step = len(samples) // 1000
            samples = samples[::step]
            result['channels'][chan.name] = {
                'values': samples,
                'downsampled': True,
                'original_length': node.numSamples,
            }
        else:
            result['channels'][chan.name] = {
                'values': samples,
                'downsampled': False,
            }

    return result


def handle_geometry_data(body):
    """Read geometry data from a SOP or POP."""
    path = body.get('path')
    include_points = body.get('include_points', True)
    include_prims = body.get('include_prims', False)
    limit = body.get('limit', 500)

    if not path:
        return {'error': 'Missing required field: path'}

    node = op(path)
    if node is None:
        return {'error': f'Node not found: {path}'}

    is_sop = bool(getattr(node, 'isSOP', False))
    is_pop = bool(getattr(node, 'isPOP', False))
    if not (is_sop or is_pop):
        return {'error': f'Node is not a SOP/POP geometry operator: {path}'}

    def _safe_count(attr_name):
        value = getattr(node, attr_name, 0)
        if callable(value):
            try:
                value = value()
            except Exception:
                return 0
        try:
            return int(value or 0)
        except Exception:
            return 0

    family = 'POP' if is_pop and not is_sop else 'SOP'
    num_points = _safe_count('numPoints')
    num_prims = _safe_count('numPrims')
    num_vertices = _safe_count('numVertices')

    result = {
        'path': path,
        'family': family,
        'numPoints': num_points,
        'numPrims': num_prims,
        'numVertices': num_vertices,
    }

    if include_points:
        points_iter = []
        points_attr = getattr(node, 'points', None)
        if points_attr is not None:
            try:
                points_iter = points_attr() if callable(points_attr) else points_attr
            except Exception:
                points_iter = []

        def _point_xyz(point):
            if all(hasattr(point, k) for k in ('x', 'y', 'z')):
                return float(point.x), float(point.y), float(point.z)
            for attr in ('P', 'position', 'pos'):
                if not hasattr(point, attr):
                    continue
                value = getattr(point, attr)
                try:
                    if callable(value):
                        value = value()
                    if isinstance(value, (tuple, list)) and len(value) >= 3:
                        return float(value[0]), float(value[1]), float(value[2])
                except Exception:
                    continue
            try:
                return float(point[0]), float(point[1]), float(point[2])
            except Exception:
                return None

        points = []
        for i, pt in enumerate(points_iter):
            if i >= limit:
                break
            point_data = {'index': int(getattr(pt, 'index', i))}
            xyz = _point_xyz(pt)
            if xyz is not None:
                point_data['x'] = xyz[0]
                point_data['y'] = xyz[1]
                point_data['z'] = xyz[2]
            else:
                point_data['raw'] = str(pt)
            points.append(point_data)
        result['points'] = points
        result['points_truncated'] = num_points > limit

    if include_prims:
        prims = []
        prims_attr = getattr(node, 'prims', None)
        if prims_attr is not None:
            try:
                prims_iter = prims_attr() if callable(prims_attr) else prims_attr
            except Exception:
                prims_iter = []
            for i, prim in enumerate(prims_iter):
                if i >= limit:
                    break
                # TD's Prim objects expose vertex count via len(prim), not a
                # numVertices attribute. The old getattr lookup always returned
                # the default 0 because TD never added that name. See N4 audit.
                try:
                    vert_count = int(len(prim))
                except Exception:
                    vert_count = int(getattr(prim, 'numVertices', 0) or 0)
                prims.append({
                    'index': int(getattr(prim, 'index', i)),
                    'numVertices': vert_count,
                })
        result['prims'] = prims
        result['prims_truncated'] = num_prims > limit

    return result


def handle_pop_inspect(body):
    """Read POP-specific metadata and attribute samples."""
    path = body.get('path')
    if not path:
        return {'error': 'Missing required field: path'}

    node = op(path)
    if node is None:
        return {'error': f'Node not found: {path}'}
    if not bool(getattr(node, 'isPOP', False)):
        return {'error': f'Node is not a POP: {path}'}

    include_bounds = bool(body.get('include_bounds', True))
    include_attributes = bool(body.get('include_attributes', True))
    start = max(0, int(body.get('start', 0) or 0))
    count = max(1, min(int(body.get('count', 32) or 32), 2048))
    delayed = bool(body.get('delayed', False))

    point_descriptors = _collect_attribute_descriptors(getattr(node, 'pointAttributes', []))
    prim_descriptors = _collect_attribute_descriptors(getattr(node, 'primAttributes', []))
    vert_descriptors = _collect_attribute_descriptors(getattr(node, 'vertAttributes', []))

    point_names = _attribute_names(point_descriptors)
    prim_names = _attribute_names(prim_descriptors)
    vert_names = _attribute_names(vert_descriptors)

    requested_point = body.get('point_attributes')
    requested_prim = body.get('prim_attributes')
    requested_vert = body.get('vert_attributes')

    if not isinstance(requested_point, list):
        requested_point = _pick_default_pop_samples(point_names)
    if not isinstance(requested_prim, list):
        requested_prim = []
    if not isinstance(requested_vert, list):
        requested_vert = []

    payload = {
        'path': path,
        'family': 'POP',
        'summary': {
            'numPoints': _safe_td_call(node, 'numPoints', delayed) or 0,
            'numPointsAllocated': _safe_td_call(node, 'numPoints', False, True) or 0,
            'numPrims': _safe_td_call(node, 'numPrims', delayed) or 0,
            'numPrimsAllocated': _safe_td_call(node, 'numPrims', False, True) or 0,
            'numVerts': _safe_td_call(node, 'numVerts', delayed) or 0,
            'numVertsAllocated': _safe_td_call(node, 'numVerts', False, True) or 0,
            'dimension': str(getattr(node, 'dimension', '')),
            'maxVertsPerLineStrip': _safe_td_call(node, 'maxVertsPerLineStrip') or 0,
        },
        'sampling': {
            'start': start,
            'count': count,
            'delayed': delayed,
        },
    }

    if include_bounds:
        payload['bounds'] = _serialize_bounds(_safe_td_call(node, 'computeBounds', False, False, delayed))

    if include_attributes:
        payload['attributes'] = {
            'point': point_descriptors,
            'point_changed': _collect_attribute_descriptors(getattr(node, 'pointAttributesChanged', [])),
            'prim': prim_descriptors,
            'prim_changed': _collect_attribute_descriptors(getattr(node, 'primAttributesChanged', [])),
            'vert': vert_descriptors,
            'vert_changed': _collect_attribute_descriptors(getattr(node, 'vertAttributesChanged', [])),
        }

    point_samples = {}
    for attr_name in requested_point:
        if attr_name in point_names:
            point_samples[attr_name] = _sample_pop_attribute(node, 'points', attr_name, start, count, delayed)

    prim_samples = {}
    for attr_name in requested_prim:
        if attr_name in prim_names:
            prim_samples[attr_name] = _sample_pop_attribute(node, 'prims', attr_name, start, count, delayed)

    vert_samples = {}
    for attr_name in requested_vert:
        if attr_name in vert_names:
            vert_samples[attr_name] = _sample_pop_attribute(node, 'verts', attr_name, start, count, delayed)

    payload['samples'] = {
        'points': point_samples,
        'prims': prim_samples,
        'verts': vert_samples,
    }
    payload['notes'] = [
        'POP downloads can stall the GPU. Use delayed=true for repeat sampling workflows.',
        'Request only the attributes you need for debugging large particle systems.',
    ]
    return payload


def handle_cooking_info(body):
    """Get cooking/performance info for a node."""
    path = body.get('path', '/')
    recurse = body.get('recurse', False)
    sort_by = body.get('sort_by', 'cookTime')  # cookTime, cpuCookTime
    limit = body.get('limit', 20)

    node = op(path)
    if node is None:
        return {'error': f'Node not found: {path}'}

    results = []

    def collect_cook(n):
        try:
            results.append({
                'path': n.path,
                'name': n.name,
                'type': n.type,
                'cookTime': n.cookTime if hasattr(n, 'cookTime') else 0,
                'cpuCookTime': n.cpuCookTime if hasattr(n, 'cpuCookTime') else 0,
                'cookFrame': n.cookFrame if hasattr(n, 'cookFrame') else 0,
            })
        except Exception:
            # Skip nodes that can't provide cook info (e.g., locked or internal)
            pass  # intentional — not all nodes expose cook timing
        if recurse and n.isCOMP:
            for child in n.children:
                collect_cook(child)

    collect_cook(node)

    # Sort
    results.sort(key=lambda x: x.get(sort_by, 0), reverse=True)
    results = results[:limit]

    return {
        'path': path,
        'fps': project.cookRate,
        'realTime': project.realTime,
        'frame': absTime.frame,
        'total_nodes': len(results),
        'nodes': results,
    }


def handle_search_nodes(body):
    """Search for nodes by name, type, or family."""
    query = body.get('query', '')
    search_path = body.get('path', '/')
    search_type = body.get('search_type', 'name')  # name, type, family, all
    limit = body.get('limit', 50)

    if not query:
        return {'error': 'Missing required field: query'}

    root = op(search_path)
    if root is None:
        return {'error': f'Search root not found: {search_path}'}

    query_lower = query.lower()
    results = []

    def search_recursive(n):
        if len(results) >= limit:
            return

        match = False
        if search_type in ('name', 'all') and query_lower in n.name.lower():
            match = True
        if search_type in ('type', 'all') and query_lower in n.type.lower():
            match = True
        if search_type in ('family', 'all') and query_lower in n.family.lower():
            match = True

        if match:
            results.append(_serialize_op(n))

        if n.isCOMP:
            for child in n.children:
                search_recursive(child)

    search_recursive(root)

    return {'query': query, 'search_type': search_type, 'count': len(results), 'nodes': results}


def handle_list_families(body):
    """List available operator families and types."""
    path = body.get('path', '/')

    root = op(path)
    if root is None:
        return {'error': f'Node not found: {path}'}

    families = {}

    def collect_types(n):
        fam = n.family
        if fam not in families:
            families[fam] = set()
        families[fam].add(n.type)
        if n.isCOMP:
            for child in n.children:
                collect_types(child)

    collect_types(root)

    return {
        'families': {k: sorted(list(v)) for k, v in sorted(families.items())},
    }


def handle_python_help(body):
    """Get Python help() output for a TD module/class."""
    target = body.get('target', '')
    if not target:
        return {'error': 'Missing required field: target (e.g. "td", "td.OP", "tdu")'}

    # Security: only allow dotted identifiers — no arbitrary expressions
    import re as _re_mod
    if not _re_mod.match(r'^[A-Za-z_][A-Za-z0-9_.]*$', target):
        return {'error': 'Invalid target: must be a dotted identifier like "td.OP" or "tdu"'}

    import io
    old_stdout = sys.stdout
    captured = io.StringIO()
    sys.stdout = captured

    try:
        # Resolve via getattr chain instead of eval for safety
        parts = target.split('.')
        obj = eval(parts[0])  # only the root identifier
        for attr in parts[1:]:
            obj = getattr(obj, attr)
        help(obj)
    except Exception as e:
        sys.stdout = old_stdout
        return {'error': f'Help failed for "{target}": {str(e)}'}
    finally:
        sys.stdout = old_stdout

    help_text = captured.getvalue()
    # Truncate if too long
    if len(help_text) > 10000:
        help_text = help_text[:10000] + '\n\n... (truncated, use more specific target)'

    return {'target': target, 'help': help_text}


def handle_python_classes(body):
    """List available TouchDesigner Python classes."""
    try:
        import td
        classes = [name for name in dir(td) if not name.startswith('_')]
        return {'module': 'td', 'classes': classes, 'count': len(classes)}
    except Exception as e:
        return {'error': f'Failed to list classes: {str(e)}'}


def _project_lifecycle_status():
    modified = getattr(project, 'modified', [])
    try:
        modified_count = len(modified)
    except Exception:
        modified_count = 0

    undo_obj = getattr(ui, 'undo', None)
    undo_stack = list(getattr(undo_obj, 'undoStack', []) or []) if undo_obj is not None else []
    redo_stack = list(getattr(undo_obj, 'redoStack', []) or []) if undo_obj is not None else []

    return {
        'project': {
            'name': str(getattr(project, 'name', '')),
            'folder': str(getattr(project, 'folder', '')),
            'saveVersion': str(getattr(project, 'saveVersion', '')),
            'saveBuild': str(getattr(project, 'saveBuild', '')),
            'modifiedCount': modified_count,
        },
        'undo': {
            'state': bool(getattr(undo_obj, 'state', False)) if undo_obj is not None else False,
            'globalState': bool(getattr(undo_obj, 'globalState', False)) if undo_obj is not None else False,
            'undoStack': undo_stack,
            'redoStack': redo_stack,
        },
    }


def handle_project_lifecycle(body):
    """Inspect and control save/load/undo lifecycle operations."""
    action = str(body.get('action', 'status')).strip().lower() or 'status'
    path = body.get('path')
    save_external_toxs = bool(body.get('save_external_toxs', False))
    undo_obj = getattr(ui, 'undo', None)

    if action == 'status':
        payload = {'success': True, 'action': action}
        payload.update(_project_lifecycle_status())
        return payload

    try:
        if action == 'save':
            if path:
                saved = project.save(path, saveExternalToxs=save_external_toxs)
            else:
                saved = project.save(saveExternalToxs=save_external_toxs)
            payload = {
                'success': bool(saved),
                'action': action,
                'path': path or str(getattr(project, 'name', '')),
                'save_external_toxs': save_external_toxs,
            }
            payload.update(_project_lifecycle_status())
            return payload

        if action == 'load':
            if not path:
                return {'error': 'Path is required for action=load'}
            project.load(path)
            payload = {'success': True, 'action': action, 'path': path}
            payload.update(_project_lifecycle_status())
            return payload

        if undo_obj is None:
            return {'error': 'ui.undo is unavailable in this TouchDesigner build/context'}

        soft_warning = None
        if action == 'undo':
            undo_obj.undo()
        elif action == 'redo':
            undo_obj.redo()
        elif action == 'start_undo_block':
            undo_obj.startBlock(body.get('name') or 'TDPilot Edit', enable=bool(body.get('enable', True)))
        elif action == 'end_undo_block':
            # TD auto-closes the active block on certain cascading mutations
            # (e.g. deleting the parent COMP that contained the block scope).
            # Calling endBlock() on an already-closed block raises "Cannot
            # end non existent undo operation". Treat that as a no-op with a
            # soft warning instead of a hard failure — the block is already
            # closed, which is the caller's desired end state.
            try:
                undo_obj.endBlock()
            except Exception as block_exc:
                msg = str(block_exc).lower()
                if 'non existent' in msg or 'nonexistent' in msg or 'no undo' in msg:
                    soft_warning = (
                        'Undo block was already closed (TouchDesigner auto-closes '
                        'blocks on certain cascading mutations like cross-scope deletes). '
                        'Treating end_undo_block as idempotent.'
                    )
                else:
                    raise
        elif action == 'clear_undo':
            undo_obj.clear()
        else:
            return {'error': f'Unknown project lifecycle action: {action}'}

        payload = {'success': True, 'action': action}
        if soft_warning is not None:
            payload['warning'] = soft_warning
        payload.update(_project_lifecycle_status())
        return payload
    except Exception as exc:
        return {'error': f'Project lifecycle action failed: {str(exc)}', 'action': action}


def handle_timeline(body):
    """Get timeline/playback state."""
    timeline = None
    try:
        timeline = (op('/project1') or op('/')).time
    except Exception:
        timeline = None

    frame = absTime.frame
    seconds = absTime.seconds
    playing = project.realTime
    fps = project.cookRate
    start = project.cookRange[0] if hasattr(project, 'cookRange') else 1
    end = project.cookRange[1] if hasattr(project, 'cookRange') else 600

    if timeline is not None:
        for attr, target in (
            ('frame', 'frame'),
            ('seconds', 'seconds'),
            ('play', 'playing'),
            ('rate', 'fps'),
            ('start', 'start'),
            ('end', 'end'),
        ):
            try:
                value = getattr(timeline, attr)
            except Exception:
                continue
            if target == 'frame':
                frame = value
            elif target == 'seconds':
                seconds = value
            elif target == 'playing':
                playing = value
            elif target == 'fps':
                fps = value
            elif target == 'start':
                start = value
            elif target == 'end':
                end = value

    return {
        'frame': frame,
        'seconds': seconds,
        'playing': playing,
        'fps': fps,
        'start': start,
        'end': end,
    }


def handle_timeline_set(body):
    """Control timeline playback."""
    action = body.get('action')  # play, pause, frame
    frame = body.get('frame', None)
    fps = body.get('fps', None)
    timeline = None
    try:
        timeline = (op('/project1') or op('/')).time
    except Exception:
        timeline = None

    if action == 'play':
        if timeline is not None:
            try:
                timeline.play = True
            except Exception:
                project.realTime = True
        else:
            project.realTime = True
        return {'success': True, 'playing': True}
    elif action == 'pause':
        if timeline is not None:
            try:
                timeline.play = False
            except Exception:
                project.realTime = False
        else:
            project.realTime = False
        return {'success': True, 'playing': False}
    elif action == 'frame' and frame is not None:
        target = int(frame)
        if timeline is not None:
            try:
                timeline.frame = target
                return {'success': True, 'frame': timeline.frame}
            except Exception:
                pass
        try:
            absTime.frame = target
            return {'success': True, 'frame': absTime.frame}
        except Exception as e:
            return {'error': f'Failed to set frame: {str(e)}'}
    elif fps is not None:
        if timeline is not None:
            try:
                timeline.rate = float(fps)
            except Exception:
                pass
        project.cookRate = fps
        return {'success': True, 'fps': project.cookRate}
    else:
        return {'error': 'Provide action (play/pause/frame) or fps'}


def handle_pulse_param(body):
    """Pulse a pulse-type parameter."""
    path = body.get('path')
    param_name = body.get('param')

    if not path or not param_name:
        return {'error': 'Missing required fields: path and param'}

    node = op(path)
    if node is None:
        return {'error': f'Node not found: {path}'}

    p = getattr(node.par, param_name, None)
    if p is None:
        return {'error': f'Parameter not found: {param_name} on {path}'}

    try:
        p.pulse()
        return {'success': True, 'path': path, 'param': param_name}
    except Exception as e:
        return {'error': f'Failed to pulse: {str(e)}'}


def _monitor_safe_name(value):
    token = re.sub(r'[^A-Za-z0-9_]+', '_', value).strip('_')
    return (token or 'monitor')[:80]


def _monitor_root():
    host = me.parent() if hasattr(me, 'parent') else None
    if host is None:
        host = op('/project1')
    if host is None or not host.isCOMP:
        return None

    root = host.op('mcp_monitors')
    if root is not None:
        return root

    root = host.create('baseCOMP', 'mcp_monitors')
    root.comment = 'Auto-generated by TD MCP monitor provisioning'
    try:
        root.nodeX = me.nodeX + 300
        root.nodeY = me.nodeY
    except Exception:
        pass
    return root


def _set_first_par(node, names, value):
    for name in names:
        p = getattr(node.par, name, None)
        if p is None:
            continue
        try:
            p.val = value
        except Exception:
            try:
                setattr(node.par, name, value)
            except Exception:
                continue
        return True
    return False


def _create_or_replace(parent, node_type, name):
    existing = parent.op(name)
    if existing is not None:
        existing.destroy()
    return parent.create(node_type, name)


def _create_with_fallback(parent, node_types, name):
    last_error = None
    for node_type in node_types:
        try:
            return _create_or_replace(parent, node_type, name)
        except Exception as exc:
            last_error = exc
    raise Exception(f'Could not create DAT {name}: {last_error}')


def _destroy_monitor_nodes(paths):
    removed = []
    for node_path in paths:
        node = op(node_path)
        if node is None:
            continue
        try:
            node.destroy()
            removed.append(node_path)
        except Exception:
            continue
    return removed


def _render_chop_callback(path, channels, threshold, rate_limit):
    channels_json = repr(channels or [])
    threshold_json = repr(threshold)
    rate_limit_val = float(rate_limit or 0.0)
    return f"""import json
import time

_CHANNELS = {channels_json}
_THRESHOLD = {threshold_json}
_RATE_LIMIT = {rate_limit_val}
_LAST_EMIT = {{}}


def _json_safe(value):
    if isinstance(value, (int, float, str, bool)) or value is None:
        return value
    return str(value)


def _emit(event_type, data, key):
    now = time.time()
    previous = _LAST_EMIT.get(key, 0.0)
    if _RATE_LIMIT > 0 and now - previous < _RATE_LIMIT:
        return
    _LAST_EMIT[key] = now
    payload = {{
        "type": event_type,
        "timestamp": now,
        "data": data,
    }}

    ws = op("/project1/mcp_server/ws_client") or op("ws_client")
    if ws is not None and hasattr(ws, "sendText"):
        try:
            ws.sendText(json.dumps(payload))
            return
        except Exception:
            pass

    try:
        emitter = mod("event_emitter")
        if hasattr(emitter, "emit_event"):
            emitter.emit_event(payload)
    except Exception:
        pass


def onValueChange(channel, sampleIndex, val, prev):
    if _CHANNELS and channel.name not in _CHANNELS:
        return
    curr = float(val)
    old = float(prev)
    if _THRESHOLD is not None and abs(curr - old) < float(_THRESHOLD):
        return
    _emit(
        "chop_change",
        {{
            "path": "{path}",
            "channel": channel.name,
            "value": _json_safe(curr),
            "prev": _json_safe(old),
        }},
        "{path}:" + channel.name,
    )
    return
"""


def _render_chop_poll_callback(path, channels, threshold, rate_limit):
    channels_json = repr(channels or [])
    threshold_json = repr(threshold)
    rate_limit_val = float(rate_limit or 0.0)
    return f"""import json
import time

_PATH = {json.dumps(path)}
_CHANNELS = {channels_json}
_THRESHOLD = {threshold_json}
_RATE_LIMIT = {rate_limit_val}
_LAST_EMIT = {{}}
_LAST_VALUES = {{}}


def _json_safe(value):
    if isinstance(value, (int, float, str, bool)) or value is None:
        return value
    return str(value)


def _emit(event_type, data, key):
    now = time.time()
    previous = _LAST_EMIT.get(key, 0.0)
    if _RATE_LIMIT > 0 and now - previous < _RATE_LIMIT:
        return
    _LAST_EMIT[key] = now
    payload = {{
        "type": event_type,
        "timestamp": now,
        "data": data,
    }}

    ws = op("/project1/mcp_server/ws_client") or op("ws_client")
    if ws is not None and hasattr(ws, "sendText"):
        try:
            ws.sendText(json.dumps(payload))
            return
        except Exception:
            pass

    try:
        emitter = mod("event_emitter")
        if hasattr(emitter, "emit_event"):
            emitter.emit_event(payload)
    except Exception:
        pass


def onFrameStart(frame):
    node = op(_PATH)
    if node is None or not getattr(node, "isCHOP", False):
        return

    for channel in node.chans():
        name = channel.name
        if _CHANNELS and name not in _CHANNELS:
            continue

        try:
            values = list(channel.vals)
            current = float(values[0]) if values else 0.0
        except Exception:
            continue

        previous = _LAST_VALUES.get(name)
        _LAST_VALUES[name] = current
        if previous is None:
            continue

        if _THRESHOLD is not None and abs(current - float(previous)) < float(_THRESHOLD):
            continue

        _emit(
            "chop_change",
            {{
                "path": _PATH,
                "channel": name,
                "value": _json_safe(current),
                "prev": _json_safe(previous),
            }},
            _PATH + ":" + name,
        )
    return
"""


def _render_par_callback(path, params, threshold, rate_limit):
    params_json = repr(params or [])
    threshold_json = repr(threshold)
    rate_limit_val = float(rate_limit or 0.0)
    return f"""import json
import time

_PARAMS = {params_json}
_THRESHOLD = {threshold_json}
_RATE_LIMIT = {rate_limit_val}
_LAST_EMIT = {{}}


def _json_safe(value):
    if isinstance(value, (int, float, str, bool)) or value is None:
        return value
    return str(value)


def _emit(event_type, data, key):
    now = time.time()
    previous = _LAST_EMIT.get(key, 0.0)
    if _RATE_LIMIT > 0 and now - previous < _RATE_LIMIT:
        return
    _LAST_EMIT[key] = now
    payload = {{
        "type": event_type,
        "timestamp": now,
        "data": data,
    }}

    ws = op("/project1/mcp_server/ws_client") or op("ws_client")
    if ws is not None and hasattr(ws, "sendText"):
        try:
            ws.sendText(json.dumps(payload))
            return
        except Exception:
            pass

    try:
        emitter = mod("event_emitter")
        if hasattr(emitter, "emit_event"):
            emitter.emit_event(payload)
    except Exception:
        pass


def onValueChange(par, prev):
    if _PARAMS and par.name not in _PARAMS:
        return
    current = par.eval()
    if _THRESHOLD is not None and isinstance(current, (int, float)) and isinstance(prev, (int, float)):
        if abs(float(current) - float(prev)) < float(_THRESHOLD):
            return
    _emit(
        "par_change",
        {{
            "path": "{path}",
            "name": par.name,
            "value": _json_safe(current),
            "prev": _json_safe(prev),
        }},
        "{path}:" + par.name,
    )
    return


def onPulse(par):
    if _PARAMS and par.name not in _PARAMS:
        return
    _emit(
        "par_change",
        {{
            "path": "{path}",
            "name": par.name,
            "value": _json_safe(par.eval()),
            "pulse": True,
        }},
        "{path}:" + par.name + ":pulse",
    )
    return
"""


def _render_runtime_callback(path, event_types, rate_limit):
    event_types_json = repr(event_types or [])
    rate_limit_val = float(rate_limit or 0.0)
    return f"""import json
import time

_PATH = {json.dumps(path)}
_EVENT_TYPES = set({event_types_json})
_RATE_LIMIT = {rate_limit_val}
_LAST_EMIT = {{}}
_STATE = {{
    "cook_frame": None,
    "errors": None,
    "timeline": None,
}}


def _json_safe(value):
    if isinstance(value, (int, float, str, bool)) or value is None:
        return value
    return str(value)


def _emit(event_type, data, key):
    now = time.time()
    previous = _LAST_EMIT.get(key, 0.0)
    if _RATE_LIMIT > 0 and now - previous < _RATE_LIMIT:
        return
    _LAST_EMIT[key] = now
    payload = {{
        "type": event_type,
        "timestamp": now,
        "data": data,
    }}

    ws = op("/project1/mcp_server/ws_client") or op("ws_client")
    if ws is not None and hasattr(ws, "sendText"):
        try:
            ws.sendText(json.dumps(payload))
            return
        except Exception:
            pass

    try:
        emitter = mod("event_emitter")
        if hasattr(emitter, "emit_event"):
            emitter.emit_event(payload)
    except Exception:
        pass


def _timeline_snapshot():
    return (
        bool(project.realTime),
        int(absTime.frame),
        float(project.cookRate),
    )


def onFrameStart(frame):
    node = op(_PATH)

    if "cook_complete" in _EVENT_TYPES and node is not None:
        cook_frame = getattr(node, "cookFrame", None)
        should_emit = False
        if cook_frame is not None:
            if cook_frame != _STATE.get("cook_frame"):
                _STATE["cook_frame"] = cook_frame
                should_emit = True
        else:
            # Fallback when cookFrame is unavailable in this TD build.
            should_emit = True

        if should_emit:
            cook_time = None
            for attr in ("cookTime", "cpuCookTime", "gpuCookTime"):
                value = getattr(node, attr, None)
                if value is not None:
                    cook_time = _json_safe(value)
                    break
            _emit(
                "cook_complete",
                {{
                    "path": _PATH,
                    "frame": int(absTime.frame),
                    "cook_frame": _json_safe(cook_frame),
                    "cook_time": cook_time,
                }},
                _PATH + ":cook",
            )

    if "node_error" in _EVENT_TYPES:
        if node is None:
            state = "node_missing"
            errs = "Node missing"
            warns = ""
        else:
            try:
                errs = node.errors(recurse=False) or ""
            except Exception:
                errs = ""
            try:
                warns = node.warnings(recurse=False) or ""
            except Exception:
                warns = ""
            state = str(errs) + "|" + str(warns)

        if state != _STATE.get("errors"):
            _STATE["errors"] = state
            if errs or warns:
                _emit(
                    "node_error",
                    {{
                        "path": _PATH,
                        "errors": _json_safe(errs),
                        "warnings": _json_safe(warns),
                    }},
                    _PATH + ":error",
                )

    if "timeline" in _EVENT_TYPES:
        timeline = _timeline_snapshot()
        if timeline != _STATE.get("timeline"):
            _STATE["timeline"] = timeline
            _emit(
                "timeline",
                {{
                    "playing": bool(project.realTime),
                    "frame": int(absTime.frame),
                    "seconds": float(absTime.seconds),
                    "fps": float(project.cookRate),
                }},
                "timeline:state",
            )
    return
"""


def _provision_monitor_nodes(node, config):
    root = _monitor_root()
    if root is None:
        raise Exception('Unable to resolve monitor root COMP.')

    created = []
    warnings = []
    base = _monitor_safe_name(config['path'].strip('/'))
    event_types = config.get('event_types', [])

    if 'chop_change' in event_types:
        if not node.isCHOP:
            warnings.append('chop_change requested on non-CHOP node; skipped.')
        else:
            cb_name = f'{base}_chop_cb'
            exec_name = f'{base}_chop_exec'
            callback_dat = _create_or_replace(root, 'textDAT', cb_name)
            try:
                callback_dat.text = _render_chop_callback(
                    config['path'],
                    config.get('channels'),
                    config.get('threshold'),
                    config.get('rate_limit', 0.016),
                )
                chop_exec = _create_with_fallback(root, ('chopExecuteDAT', 'chopexecDAT'), exec_name)
                _set_first_par(chop_exec, ('active',), 1)
                _set_first_par(chop_exec, ('chop',), config['path'])
                _set_first_par(chop_exec, ('valuechange', 'onvaluechange'), 1)
                _set_first_par(chop_exec, ('callbacks', 'callbackdat', 'callback'), callback_dat.path)
                created.extend([callback_dat.path, chop_exec.path])
            except Exception:
                callback_dat.text = _render_chop_poll_callback(
                    config['path'],
                    config.get('channels'),
                    config.get('threshold'),
                    config.get('rate_limit', 0.016),
                )
                exec_dat = _create_with_fallback(root, ('executeDAT',), exec_name)
                _set_first_par(exec_dat, ('active',), 1)
                _set_first_par(exec_dat, ('framestart', 'onframestart', 'frameStart'), 1)
                _set_first_par(exec_dat, ('callbacks', 'callbackdat', 'callback'), callback_dat.path)
                try:
                    exec_dat.text = callback_dat.text
                except Exception:
                    pass
                created.extend([callback_dat.path, exec_dat.path])
                warnings.append('chopExecuteDAT unavailable; using executeDAT polling fallback.')

    if 'par_change' in event_types:
        cb_name = f'{base}_par_cb'
        exec_name = f'{base}_par_exec'
        callback_dat = _create_or_replace(root, 'textDAT', cb_name)
        callback_dat.text = _render_par_callback(
            config['path'],
            config.get('params'),
            config.get('threshold'),
            config.get('rate_limit', 0.016),
        )
        par_exec = _create_with_fallback(root, ('parameterexecuteDAT', 'parexecDAT'), exec_name)
        _set_first_par(par_exec, ('active',), 1)
        _set_first_par(par_exec, ('op', 'ops', 'targetop'), config['path'])
        _set_first_par(par_exec, ('pars', 'parameters'), ' '.join(config.get('params') or []))
        _set_first_par(par_exec, ('valuechange', 'onvaluechange'), 1)
        _set_first_par(par_exec, ('onpulse', 'pulse'), 1)
        _set_first_par(par_exec, ('callbacks', 'callbackdat', 'callback'), callback_dat.path)
        created.extend([callback_dat.path, par_exec.path])

    runtime_types = [
        event for event in ('cook_complete', 'node_error', 'timeline')
        if event in event_types
    ]
    if runtime_types:
        cb_name = f'{base}_runtime_cb'
        exec_name = f'{base}_runtime_exec'
        callback_dat = _create_or_replace(root, 'textDAT', cb_name)
        callback_dat.text = _render_runtime_callback(
            config['path'],
            runtime_types,
            config.get('rate_limit', 0.016),
        )
        try:
            exec_dat = _create_with_fallback(root, ('executeDAT',), exec_name)
            _set_first_par(exec_dat, ('active',), 1)
            _set_first_par(exec_dat, ('framestart', 'onframestart', 'frameStart'), 1)
            _set_first_par(exec_dat, ('callbacks', 'callbackdat', 'callback'), callback_dat.path)
            try:
                exec_dat.text = callback_dat.text
            except Exception:
                pass
            created.extend([callback_dat.path, exec_dat.path])
        except Exception as exc:
            warnings.append(f'Failed to provision runtime monitor DAT: {exc}')

    return created, warnings


def handle_monitor_subscribe(body):
    """Create/update monitor DATs for real-time event subscription."""
    path = body.get('path')
    if not path:
        return {'error': 'Missing required field: path'}

    node = op(path)
    if node is None:
        return {'error': f'Node not found: {path}'}

    existing = MONITOR_SUBSCRIPTIONS.get(path, {})
    if existing.get('monitor_nodes'):
        _destroy_monitor_nodes(existing.get('monitor_nodes', []))

    config = {
        'path': path,
        'event_types': body.get('event_types', ['chop_change', 'par_change']),
        'channels': body.get('channels'),
        'params': body.get('params'),
        'threshold': body.get('threshold'),
        'rate_limit': body.get('rate_limit', 0.016),
    }

    try:
        monitor_nodes, warnings = _provision_monitor_nodes(node, config)
    except Exception as exc:
        return {'error': f'Failed to provision monitors: {str(exc)}'}

    MONITOR_SUBSCRIPTIONS[path] = {
        'config': config,
        'monitor_nodes': monitor_nodes,
        'created_at': time.time(),
    }

    return {
        'success': True,
        'monitoring': config,
        'monitor_nodes': monitor_nodes,
        'warnings': warnings,
        'active_subscriptions': len(MONITOR_SUBSCRIPTIONS),
    }


def handle_monitor_unsubscribe(body):
    """Remove monitor DATs and subscription state for a path."""
    path = body.get('path')
    if not path:
        return {'error': 'Missing required field: path'}

    removed = MONITOR_SUBSCRIPTIONS.pop(path, None)
    destroyed = []
    if removed:
        destroyed = _destroy_monitor_nodes(removed.get('monitor_nodes', []))

    return {
        'success': removed is not None,
        'path': path,
        'destroyed_nodes': destroyed,
        'active_subscriptions': len(MONITOR_SUBSCRIPTIONS),
    }


def handle_analyze_frame(body):
    """Analyze pixel data of a TOP node using numpy.

    Supported modes: histogram, luminance, alpha_coverage, color_dominant, roi_diff.
    Returns per-mode result dicts plus resolution metadata.
    """
    path = body.get('path')
    if not path:
        return {'error': 'Missing required field: path'}

    modes = body.get('modes', ['histogram', 'luminance'])
    if not isinstance(modes, list) or len(modes) == 0:
        modes = ['histogram', 'luminance']

    top = op(path)
    if top is None:
        return {'error': f'Node not found: {path}'}
    if not top.isTOP:
        return {'error': f'Node is not a TOP: {path} (type: {top.type})'}

    try:
        np = sys.modules.get('numpy')
        if np is None:
            import importlib
            np = importlib.import_module('numpy')
    except Exception as exc:
        return {'error': f'numpy not available: {str(exc)}'}

    try:
        arr = top.numpyArray()
    except Exception as exc:
        return {'error': f'Could not get pixel data: {str(exc)}'}

    if arr is None:
        return {'error': f'numpyArray() returned None for: {path}'}

    # Ensure 3D array — grayscale TOPs may return 2D (H, W) without channel axis
    if arr.ndim == 2:
        arr = arr[:, :, None]

    h, w = arr.shape[:2]
    num_channels = arr.shape[2]

    if h == 0 or w == 0:
        return {'error': f'Image has zero pixels ({w}x{h})', 'path': path}

    mode_results = {}

    for mode in modes:
        try:
            if mode == 'histogram':
                rgb = arr[:, :, :3] if num_channels >= 3 else arr[:, :, :1]
                bins = 16
                hists = {}
                chan_names = ['r', 'g', 'b'] if num_channels >= 3 else ['l']
                for i, name in enumerate(chan_names):
                    channel = rgb[:, :, i].flatten()
                    counts, edges = np.histogram(channel, bins=bins, range=(0.0, 1.0))
                    hists[name] = {
                        'counts': counts.tolist(),
                        'edges': [round(float(e), 4) for e in edges.tolist()],
                    }
                mode_results['histogram'] = {'bins': bins, 'channels': hists}

            elif mode == 'luminance':
                if num_channels >= 3:
                    lum = (0.2126 * arr[:, :, 0]
                           + 0.7152 * arr[:, :, 1]
                           + 0.0722 * arr[:, :, 2])
                else:
                    lum = arr[:, :, 0]
                mode_results['luminance'] = {
                    'mean': float(np.mean(lum)),
                    'min': float(np.min(lum)),
                    'max': float(np.max(lum)),
                    'std': float(np.std(lum)),
                    'p5': float(np.percentile(lum, 5)),
                    'p95': float(np.percentile(lum, 95)),
                }

            elif mode == 'alpha_coverage':
                if num_channels >= 4:
                    alpha = arr[:, :, 3]
                    total_pixels = h * w
                    above_half = int(np.sum(alpha > 0.5))
                    mode_results['alpha_coverage'] = {
                        'mean_alpha': float(np.mean(alpha)),
                        'opaque_fraction': above_half / float(total_pixels) if total_pixels > 0 else 0.0,
                        'fully_transparent_fraction': float(np.mean(alpha < 0.01)),
                    }
                else:
                    mode_results['alpha_coverage'] = {'error': f'No alpha channel (channels={num_channels})'}

            elif mode == 'color_dominant':
                if num_channels >= 3:
                    rgb_flat = arr[:, :, :3].reshape(-1, 3)
                    # quantize to 4-bit per channel (16 levels) then find mode
                    quantized = (rgb_flat * 15).astype(np.uint8)
                    # Use np.unique instead of pure-Python loop (orders of magnitude faster)
                    unique_colors, color_counts = np.unique(quantized, axis=0, return_counts=True)
                    best_idx = int(np.argmax(color_counts))
                    dominant_q = unique_colors[best_idx]
                    dominant = [round(float(c) / 15.0, 3) for c in dominant_q]
                    best_count = int(color_counts[best_idx])
                    mode_results['color_dominant'] = {
                        'rgb': dominant,
                        'hex': f'#{int(dominant[0] * 255):02x}{int(dominant[1] * 255):02x}{int(dominant[2] * 255):02x}',
                        'pixel_count': best_count,
                        'fraction': round(best_count / float(h * w), 4) if h * w > 0 else 0.0,
                    }
                else:
                    mode_results['color_dominant'] = {'error': 'Need at least 3 channels for color_dominant'}

            elif mode == 'roi_diff':
                roi = body.get('roi')
                reference_path = body.get('reference_path')
                if roi is None or reference_path is None:
                    mode_results['roi_diff'] = {
                        'error': 'roi_diff requires roi=[x,y,w,h] and reference_path in request body'
                    }
                else:
                    rx, ry, rw, rh = int(roi[0]), int(roi[1]), int(roi[2]), int(roi[3])
                    # Clamp to image bounds
                    rx = max(0, min(rx, w - 1))
                    ry = max(0, min(ry, h - 1))
                    rw = max(1, min(rw, w - rx))
                    rh = max(1, min(rh, h - ry))

                    ref_top = op(reference_path)
                    if ref_top is None:
                        mode_results['roi_diff'] = {'error': f'Reference node not found: {reference_path}'}
                    elif not ref_top.isTOP:
                        mode_results['roi_diff'] = {'error': f'Reference is not a TOP: {reference_path}'}
                    else:
                        ref_arr = ref_top.numpyArray()
                        if ref_arr is None:
                            mode_results['roi_diff'] = {'error': 'Reference numpyArray() returned None'}
                        elif ref_arr.ndim == 2:
                            ref_arr = ref_arr[:, :, None]
                        if ref_arr is not None and ref_arr.ndim >= 3:
                            patch_a = arr[ry:ry + rh, rx:rx + rw, :3].astype(float)
                            ref_h, ref_w = ref_arr.shape[:2]
                            ref_rx = max(0, min(rx, ref_w - 1))
                            ref_ry = max(0, min(ry, ref_h - 1))
                            ref_rw = max(1, min(rw, ref_w - ref_rx))
                            ref_rh = max(1, min(rh, ref_h - ref_ry))
                            patch_b = ref_arr[ref_ry:ref_ry + ref_rh, ref_rx:ref_rx + ref_rw, :3].astype(float)
                            # Crop both patches to their common overlap size
                            if patch_a.shape != patch_b.shape:
                                min_h = min(patch_a.shape[0], patch_b.shape[0])
                                min_w = min(patch_a.shape[1], patch_b.shape[1])
                                patch_a = patch_a[:min_h, :min_w, :]
                                patch_b = patch_b[:min_h, :min_w, :]
                            diff = patch_a - patch_b
                            mode_results['roi_diff'] = {
                                'roi': [rx, ry, rw, rh],
                                'reference_path': reference_path,
                                'mean_abs_diff': float(np.mean(np.abs(diff))),
                                'max_abs_diff': float(np.max(np.abs(diff))),
                                'rmse': float(np.sqrt(np.mean(diff ** 2))),
                            }

            else:
                mode_results[mode] = {'error': f'Unknown mode: {mode}'}

        except Exception as exc:
            mode_results[mode] = {'error': f'Mode {mode} failed: {str(exc)}'}

    return {
        'path': path,
        'resolution': [w, h],
        'channels': num_channels,
        'modes': mode_results,
    }
