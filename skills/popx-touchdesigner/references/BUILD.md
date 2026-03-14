# Building POPx References

POPx is a paid TouchDesigner plugin by Yuval Cohen, available via [Patreon](https://www.patreon.com/popsextension). Its documentation and examples are copyrighted and cannot be redistributed.

To use the POPx skill with TDPilot, you need to generate the reference files locally from your own licensed copy.

## Prerequisites

- Active POPx Patreon subscription (Advanced tier)
- POPx installed in TouchDesigner
- A local mirror of the POPx docs site, **or** the POPx examples `.toe` file
- Python 3.11+ with `beautifulsoup4` installed (`pip install beautifulsoup4`)

## Generate References

### Option 1: From docs site mirror + example export

```bash
# 1. Export examples from TouchDesigner (run in Textport):
#    Select all nodes under /EXAMPLE_LOADER, right-click → Copy, paste into a file

# 2. Build references:
python3 scripts/build_popx_refs.py \
  --docs-dir /path/to/popx-docs-mirror \
  --export-path references/raw-example-export.pyrepr
```

### Option 2: From example export only

```bash
python3 scripts/build_popx_refs.py \
  --export-path /path/to/your-example-export.pyrepr
```

## Expected Output

After building, the `references/` directory will contain:

- `overview.md` — corpus summary
- `guides.md` — installation and tutorial content
- `operators-generators.md`, `operators-falloffs.md`, etc. — operator details
- `examples.md` — 54 example configurations with working values
- `catalog.json` — structured operator catalog

These files are gitignored and will not be committed.

## Search

Once built, search across all references:

```bash
python3 scripts/search_popx_refs.py "particle fluid"
```
