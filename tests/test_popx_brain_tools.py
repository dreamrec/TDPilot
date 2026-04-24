"""Tests for POPx brain — DocsBrain can read POPx FTS5 databases."""

import sqlite3
import tempfile
from pathlib import Path


def _create_test_popx_db(tmp_dir: Path) -> Path:
    """Create a minimal POPx brain DB for testing."""
    db_path = tmp_dir / "popxbrain.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript("""
        CREATE TABLE chunks (
            id INTEGER PRIMARY KEY, url TEXT, page_title TEXT, section_title TEXT,
            content TEXT, doc_type TEXT, chunk_type TEXT, operator_name TEXT,
            operator_family TEXT, parameter_names TEXT DEFAULT '[]',
            python_symbols TEXT DEFAULT '[]', mentioned_operators TEXT DEFAULT '[]',
            build_number TEXT, build_date TEXT, change_category TEXT, source TEXT DEFAULT 'html'
        );
        CREATE VIRTUAL TABLE chunks_fts USING fts5(
            section_title, operator_name, parameter_names, python_symbols, content, content=''
        );
        INSERT INTO chunks (url, page_title, section_title, content, doc_type, chunk_type, operator_name, operator_family)
        VALUES ('https://popsextension.com/particle', 'Particle', 'Overview',
                'GPU particle simulation with SPH, PBF, Grains modes', 'operator', 'operator', 'Particle SIM', 'SIM');
        INSERT INTO chunks_fts (rowid, section_title, operator_name, parameter_names, python_symbols, content)
        VALUES (1, 'Overview', 'Particle SIM', '[]', '[]', 'GPU particle simulation with SPH, PBF, Grains modes');
    """)
    conn.close()
    return db_path


def test_popx_brain_search():
    """DocsBrain can search a POPx brain DB."""
    from td_mcp.knowledge.docsbrain import DocsBrain

    with tempfile.TemporaryDirectory() as tmp:
        db_path = _create_test_popx_db(Path(tmp))
        brain = DocsBrain(db_path=db_path)
        results = brain.search("particle simulation")
        assert len(results) >= 1
        assert "particle" in results[0]["content"].lower()


def test_popx_brain_count():
    """DocsBrain.count() works on POPx DB."""
    from td_mcp.knowledge.docsbrain import DocsBrain

    with tempfile.TemporaryDirectory() as tmp:
        db_path = _create_test_popx_db(Path(tmp))
        brain = DocsBrain(db_path=db_path)
        assert brain.count() == 1
