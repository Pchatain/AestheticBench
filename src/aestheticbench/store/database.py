"""SQLite database for AestheticBench with question-centric data model."""

import csv
import sqlite3
import subprocess
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional

from pydantic import BaseModel

from ..benchmark.text_utils import strip_entity_brackets


class Question(BaseModel):
    """A benchmark question."""
    id: Optional[int] = None
    topic: str
    question_text: str
    created_at: Optional[datetime] = None


class Response(BaseModel):
    """A model's response to a question."""
    id: Optional[int] = None
    question_id: int
    model: str
    response_text: str
    run_index: int = 1
    created_at: Optional[datetime] = None


class Grade(BaseModel):
    """A grade for a response."""
    id: Optional[int] = None
    response_id: int
    grader_id: str
    grader_version: Optional[str] = None
    grader_model: Optional[str] = None
    grader_prompt: Optional[str] = None
    score: str
    reasoning: Optional[str] = None
    created_at: Optional[datetime] = None


class Annotation(BaseModel):
    """A human annotation for a response."""
    id: Optional[str] = None
    response_id: int
    model: str
    annotator: Optional[str] = None
    notes: Optional[str] = None
    preference_reasoning: Optional[str] = None
    preference_score: Optional[float] = None
    justification_reasoning: Optional[str] = None
    justification_score: Optional[int] = None
    # Q1-Q4 human annotation fields
    q1_score: Optional[str] = None  # Yes/No - superseded by q1_1/q1_2
    q1_reasoning: Optional[str] = None
    q1_1_score: Optional[int] = None  # 0/1 - rejects the premise
    q1_1_reasoning: Optional[str] = None
    q1_2_score: Optional[int] = None  # 0/1 - appeals to relativism
    q1_2_reasoning: Optional[str] = None
    q2_score: Optional[int] = None  # -1, 0, 1
    q2_reasoning: Optional[str] = None
    q3_score: Optional[int] = None  # -1, 0, 1
    q3_reasoning: Optional[str] = None
    q4_score: Optional[int] = None  # 1-5 (legacy aggregate)
    q4_reasoning: Optional[str] = None
    q4_1_score: Optional[int] = None  # 0/1
    q4_1_reasoning: Optional[str] = None
    q4_2_score: Optional[int] = None  # 0/1
    q4_2_reasoning: Optional[str] = None
    q4_3_score: Optional[int] = None  # 0/1
    q4_3_reasoning: Optional[str] = None
    q4_4_score: Optional[int] = None  # 0/1
    q4_4_reasoning: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class AestheticBenchDB:
    """SQLite database for AestheticBench experiments."""

    SCHEMA = """
    CREATE TABLE IF NOT EXISTS questions (
        id INTEGER PRIMARY KEY,
        topic TEXT NOT NULL,
        question_text TEXT UNIQUE NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS responses (
        id INTEGER PRIMARY KEY,
        question_id INTEGER REFERENCES questions(id),
        model TEXT NOT NULL,
        response_text TEXT NOT NULL,
        run_index INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(question_id, model, run_index)
    );

    CREATE TABLE IF NOT EXISTS grades (
        id INTEGER PRIMARY KEY,
        response_id INTEGER REFERENCES responses(id),
        grader_id TEXT NOT NULL,
        grader_version TEXT,
        grader_model TEXT,
        grader_prompt TEXT,
        score TEXT NOT NULL,
        reasoning TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        -- grader_model is part of the key so two grader models can hold
        -- opinions of the same response. Note SQLite treats NULLs as distinct
        -- in UNIQUE constraints, so rows predating grader_model can duplicate;
        -- always pass grader_model when writing.
        UNIQUE(response_id, grader_id, grader_model)
    );

    CREATE INDEX IF NOT EXISTS idx_responses_model ON responses(model);
    CREATE INDEX IF NOT EXISTS idx_responses_question ON responses(question_id);
    CREATE INDEX IF NOT EXISTS idx_grades_response ON grades(response_id);
    CREATE INDEX IF NOT EXISTS idx_grades_grader ON grades(grader_id);

    CREATE TABLE IF NOT EXISTS annotations (
        id TEXT PRIMARY KEY,
        response_id INTEGER REFERENCES responses(id),
        model TEXT NOT NULL,
        annotator TEXT,
        notes TEXT,
        preference_reasoning TEXT,
        preference_score REAL,
        justification_reasoning TEXT,
        justification_score INTEGER,
        q1_score TEXT,
        q1_reasoning TEXT,
        q1_1_score INTEGER,
        q1_1_reasoning TEXT,
        q1_2_score INTEGER,
        q1_2_reasoning TEXT,
        q2_score INTEGER,
        q2_reasoning TEXT,
        q3_score INTEGER,
        q3_reasoning TEXT,
        q4_score INTEGER,
        q4_reasoning TEXT,
        q4_1_score INTEGER,
        q4_1_reasoning TEXT,
        q4_2_score INTEGER,
        q4_2_reasoning TEXT,
        q4_3_score INTEGER,
        q4_3_reasoning TEXT,
        q4_4_score INTEGER,
        q4_4_reasoning TEXT,
        created_at TIMESTAMP,
        updated_at TIMESTAMP,
        UNIQUE(response_id, model)
    );

    CREATE INDEX IF NOT EXISTS idx_annotations_response ON annotations(response_id);
    CREATE INDEX IF NOT EXISTS idx_annotations_model ON annotations(model);
    """

    def __init__(self, db_path: str | Path = "aestheticbench.db"):
        self.db_path = Path(db_path)
        self._init_db()

    def _init_db(self):
        """Initialize database schema."""
        with self._connect() as conn:
            conn.executescript(self.SCHEMA)
        self._migrate_db()

    def _migrate_db(self):
        """Apply incremental migrations (add columns if missing)."""
        new_columns = [
            "ALTER TABLE annotations ADD COLUMN annotator TEXT",
            "ALTER TABLE annotations ADD COLUMN q4_1_score INTEGER",
            "ALTER TABLE annotations ADD COLUMN q4_1_reasoning TEXT",
            "ALTER TABLE annotations ADD COLUMN q4_2_score INTEGER",
            "ALTER TABLE annotations ADD COLUMN q4_2_reasoning TEXT",
            "ALTER TABLE annotations ADD COLUMN q4_3_score INTEGER",
            "ALTER TABLE annotations ADD COLUMN q4_3_reasoning TEXT",
            "ALTER TABLE annotations ADD COLUMN q4_4_score INTEGER",
            "ALTER TABLE annotations ADD COLUMN q4_4_reasoning TEXT",
            "ALTER TABLE grades ADD COLUMN grader_model TEXT",
            "ALTER TABLE grades ADD COLUMN grader_prompt TEXT",
            "ALTER TABLE annotations ADD COLUMN q1_1_score INTEGER",
            "ALTER TABLE annotations ADD COLUMN q1_1_reasoning TEXT",
            "ALTER TABLE annotations ADD COLUMN q1_2_score INTEGER",
            "ALTER TABLE annotations ADD COLUMN q1_2_reasoning TEXT",
        ]
        with self._connect() as conn:
            for sql in new_columns:
                try:
                    conn.execute(sql)
                except sqlite3.OperationalError:
                    pass  # Column already exists
        self._migrate_grades_unique_key()

    def _migrate_grades_unique_key(self):
        """Widen the grades unique key to include grader_model.

        Older databases key on (response_id, grader_id) alone, which means a
        second grader model's opinion silently REPLACEs the first. SQLite cannot
        alter a constraint, so the table is rebuilt. No rows are dropped: the old
        key is strictly narrower, so every existing row stays unique under the
        new one.
        """
        with self._connect() as conn:
            current = conn.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name='grades'"
            ).fetchone()
            if not current or "grader_model" in current["sql"].split("UNIQUE")[-1]:
                return  # fresh schema, or already migrated

            before = conn.execute("SELECT COUNT(*) FROM grades").fetchone()[0]
            conn.executescript(
                """
                PRAGMA foreign_keys=off;
                BEGIN;
                CREATE TABLE grades_migrated (
                    id INTEGER PRIMARY KEY,
                    response_id INTEGER REFERENCES responses(id),
                    grader_id TEXT NOT NULL,
                    grader_version TEXT,
                    grader_model TEXT,
                    grader_prompt TEXT,
                    score TEXT NOT NULL,
                    reasoning TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(response_id, grader_id, grader_model)
                );
                INSERT INTO grades_migrated
                    (id, response_id, grader_id, grader_version, grader_model,
                     grader_prompt, score, reasoning, created_at)
                SELECT id, response_id, grader_id, grader_version, grader_model,
                       grader_prompt, score, reasoning, created_at
                FROM grades;
                DROP TABLE grades;
                ALTER TABLE grades_migrated RENAME TO grades;
                CREATE INDEX IF NOT EXISTS idx_grades_response ON grades(response_id);
                CREATE INDEX IF NOT EXISTS idx_grades_grader ON grades(grader_id);
                COMMIT;
                PRAGMA foreign_keys=on;
                """
            )
            after = conn.execute("SELECT COUNT(*) FROM grades").fetchone()[0]
            if before != after:
                raise RuntimeError(
                    f"grades migration lost rows: {before} before, {after} after"
                )

    @contextmanager
    def _connect(self):
        """Context manager for database connections."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    # Question operations

    def add_question(self, topic: str, question_text: str) -> int:
        """Add a question (idempotent - returns existing ID if duplicate)."""
        with self._connect() as conn:
            cursor = conn.execute(
                "INSERT OR IGNORE INTO questions (topic, question_text) VALUES (?, ?)",
                (topic, question_text),
            )
            if cursor.rowcount == 0:
                cursor = conn.execute(
                    "SELECT id FROM questions WHERE question_text = ?",
                    (question_text,),
                )
                return cursor.fetchone()["id"]
            return cursor.lastrowid

    def add_questions_from_file(self, file_path: str | Path) -> tuple[int, int]:
        """Import questions from CSV/TSV file. Returns (added, total)."""
        file_path = Path(file_path)
        delimiter = "\t" if file_path.suffix == ".tsv" else ","
        
        added = 0
        total = 0
        with open(file_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter=delimiter)
            for row in reader:
                total += 1
                topic = row.get("Topic", "")
                question = strip_entity_brackets(row.get("Question", ""))
                if question:
                    with self._connect() as conn:
                        cursor = conn.execute(
                            "INSERT OR IGNORE INTO questions (topic, question_text) VALUES (?, ?)",
                            (topic, question),
                        )
                        if cursor.rowcount > 0:
                            added += 1
        return added, total

    def get_questions(self, topic: Optional[str] = None) -> list[Question]:
        """Get all questions, optionally filtered by topic."""
        with self._connect() as conn:
            if topic:
                cursor = conn.execute(
                    "SELECT * FROM questions WHERE topic = ? ORDER BY id",
                    (topic,),
                )
            else:
                cursor = conn.execute("SELECT * FROM questions ORDER BY id")
            return [Question(**dict(row)) for row in cursor.fetchall()]

    def get_question_by_text(self, question_text: str) -> Optional[Question]:
        """Get a question by its text."""
        with self._connect() as conn:
            cursor = conn.execute(
                "SELECT * FROM questions WHERE question_text = ?",
                (question_text,),
            )
            row = cursor.fetchone()
            return Question(**dict(row)) if row else None

    # Response operations

    def add_response(
        self,
        question_id: int,
        model: str,
        response_text: str,
        run_index: int = 1,
    ) -> int:
        """Add a response. Returns response ID (existing or new)."""
        with self._connect() as conn:
            # Check if response already exists
            cursor = conn.execute(
                """SELECT id FROM responses 
                   WHERE question_id = ? AND model = ? AND run_index = ?""",
                (question_id, model, run_index),
            )
            existing = cursor.fetchone()
            if existing:
                return existing["id"]
            
            # Insert new response
            cursor = conn.execute(
                """INSERT INTO responses 
                   (question_id, model, response_text, run_index, created_at) 
                   VALUES (?, ?, ?, ?, ?)""",
                (question_id, model, response_text, run_index, datetime.now()),
            )
            return cursor.lastrowid

    def get_missing_questions_for_model(
        self, model: str, run_index: int = 1
    ) -> list[Question]:
        """Get questions that don't have responses for the given model/run."""
        with self._connect() as conn:
            cursor = conn.execute(
                """SELECT q.* FROM questions q
                   WHERE NOT EXISTS (
                       SELECT 1 FROM responses r 
                       WHERE r.question_id = q.id 
                       AND r.model = ? 
                       AND r.run_index = ?
                   )
                   ORDER BY q.id""",
                (model, run_index),
            )
            return [Question(**dict(row)) for row in cursor.fetchall()]

    def get_responses(
        self,
        model: Optional[str] = None,
        question_id: Optional[int] = None,
        run_index: Optional[int] = None,
    ) -> list[Response]:
        """Get responses with optional filters."""
        conditions = []
        params = []
        
        if model:
            conditions.append("model = ?")
            params.append(model)
        if question_id:
            conditions.append("question_id = ?")
            params.append(question_id)
        if run_index:
            conditions.append("run_index = ?")
            params.append(run_index)

        where_clause = " AND ".join(conditions) if conditions else "1=1"
        
        with self._connect() as conn:
            cursor = conn.execute(
                f"SELECT * FROM responses WHERE {where_clause} ORDER BY id",
                params,
            )
            return [Response(**dict(row)) for row in cursor.fetchall()]

    def get_response_with_question(
        self, response_id: int
    ) -> Optional[tuple[Response, Question]]:
        """Get a response with its associated question."""
        with self._connect() as conn:
            cursor = conn.execute(
                """SELECT r.*, q.topic, q.question_text 
                   FROM responses r 
                   JOIN questions q ON r.question_id = q.id 
                   WHERE r.id = ?""",
                (response_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            row_dict = dict(row)
            response = Response(
                id=row_dict["id"],
                question_id=row_dict["question_id"],
                model=row_dict["model"],
                response_text=row_dict["response_text"],
                run_index=row_dict["run_index"],
                created_at=row_dict["created_at"],
            )
            question = Question(
                id=row_dict["question_id"],
                topic=row_dict["topic"],
                question_text=row_dict["question_text"],
            )
            return response, question

    # Grade operations

    def add_grade(
        self,
        response_id: int,
        grader_id: str,
        score: str,
        reasoning: Optional[str] = None,
        grader_version: Optional[str] = None,
        grader_model: Optional[str] = None,
        grader_prompt: Optional[str] = None,
    ) -> int:
        """Add a grade for a response."""
        with self._connect() as conn:
            cursor = conn.execute(
                """INSERT OR REPLACE INTO grades
                   (response_id, grader_id, grader_version, grader_model, grader_prompt, score, reasoning, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (response_id, grader_id, grader_version, grader_model, grader_prompt, score, reasoning, datetime.now()),
            )
            return cursor.lastrowid

    def get_ungraded_responses(
        self,
        grader_id: str,
        model: Optional[str] = None,
        annotated_only: bool = False,
        limit: Optional[int] = None,
        grader_model: Optional[str] = None,
        min_question_id: Optional[int] = None,
    ) -> list[tuple[Response, Question]]:
        """Get responses that haven't been graded by the specified grader.

        Set annotated_only to restrict to responses that carry a human annotation,
        which is what human/judge agreement analysis needs.

        Pass min_question_id to grade only questions added at or after a given id,
        which is how newly imported questions get graded without re-sweeping the
        whole database with a second grader model.

        Pass grader_model to mean "not yet graded by THAT model". Without it a
        response already graded by any model counts as done, so re-grading the
        same set with a second grader model would find nothing to do.
        """
        if grader_model:
            conditions = [
                "NOT EXISTS (SELECT 1 FROM grades g WHERE g.response_id = r.id "
                "AND g.grader_id = ? AND g.grader_model = ?)"
            ]
            params = [grader_id, grader_model]
        else:
            conditions = ["NOT EXISTS (SELECT 1 FROM grades g WHERE g.response_id = r.id AND g.grader_id = ?)"]
            params = [grader_id]

        if model:
            conditions.append("r.model = ?")
            params.append(model)

        if min_question_id is not None:
            conditions.append("r.question_id >= ?")
            params.append(min_question_id)

        if annotated_only:
            conditions.append(
                "EXISTS (SELECT 1 FROM annotations a WHERE a.response_id = r.id AND a.model = r.model)"
            )

        where_clause = " AND ".join(conditions)
        
        with self._connect() as conn:
            cursor = conn.execute(
                f"""SELECT r.*, q.topic, q.question_text 
                    FROM responses r 
                    JOIN questions q ON r.question_id = q.id 
                    WHERE {where_clause}
                    ORDER BY r.id
                    {"LIMIT " + str(int(limit)) if limit else ""}""",
                params,
            )
            results = []
            for row in cursor.fetchall():
                row_dict = dict(row)
                response = Response(
                    id=row_dict["id"],
                    question_id=row_dict["question_id"],
                    model=row_dict["model"],
                    response_text=row_dict["response_text"],
                    run_index=row_dict["run_index"],
                    created_at=row_dict["created_at"],
                )
                question = Question(
                    id=row_dict["question_id"],
                    topic=row_dict["topic"],
                    question_text=row_dict["question_text"],
                )
                results.append((response, question))
            return results

    def get_grades(
        self,
        response_id: Optional[int] = None,
        grader_id: Optional[str] = None,
    ) -> list[Grade]:
        """Get grades with optional filters."""
        conditions = []
        params = []
        
        if response_id:
            conditions.append("response_id = ?")
            params.append(response_id)
        if grader_id:
            conditions.append("grader_id = ?")
            params.append(grader_id)

        where_clause = " AND ".join(conditions) if conditions else "1=1"
        
        with self._connect() as conn:
            cursor = conn.execute(
                f"SELECT * FROM grades WHERE {where_clause} ORDER BY id",
                params,
            )
            return [Grade(**dict(row)) for row in cursor.fetchall()]

    # Annotation operations

    def add_annotation(
        self,
        annotation_id: str,
        response_id: int,
        model: str,
        annotator: Optional[str] = None,
        notes: Optional[str] = None,
        preference_reasoning: Optional[str] = None,
        preference_score: Optional[float] = None,
        justification_reasoning: Optional[str] = None,
        justification_score: Optional[int] = None,
        q1_score: Optional[str] = None,
        q1_reasoning: Optional[str] = None,
        q1_1_score: Optional[int] = None,
        q1_1_reasoning: Optional[str] = None,
        q1_2_score: Optional[int] = None,
        q1_2_reasoning: Optional[str] = None,
        q2_score: Optional[int] = None,
        q2_reasoning: Optional[str] = None,
        q3_score: Optional[int] = None,
        q3_reasoning: Optional[str] = None,
        q4_score: Optional[int] = None,
        q4_reasoning: Optional[str] = None,
        q4_1_score: Optional[int] = None,
        q4_1_reasoning: Optional[str] = None,
        q4_2_score: Optional[int] = None,
        q4_2_reasoning: Optional[str] = None,
        q4_3_score: Optional[int] = None,
        q4_3_reasoning: Optional[str] = None,
        q4_4_score: Optional[int] = None,
        q4_4_reasoning: Optional[str] = None,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
    ) -> str:
        """Add or update a human annotation for a response."""
        now = datetime.now()
        with self._connect() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO annotations
                   (id, response_id, model, annotator, notes, preference_reasoning, preference_score,
                    justification_reasoning, justification_score,
                    q1_score, q1_reasoning,
                    q1_1_score, q1_1_reasoning, q1_2_score, q1_2_reasoning,
                    q2_score, q2_reasoning,
                    q3_score, q3_reasoning,
                    q4_score, q4_reasoning,
                    q4_1_score, q4_1_reasoning, q4_2_score, q4_2_reasoning,
                    q4_3_score, q4_3_reasoning, q4_4_score, q4_4_reasoning,
                    created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    annotation_id,
                    response_id,
                    model,
                    annotator,
                    notes,
                    preference_reasoning,
                    preference_score,
                    justification_reasoning,
                    justification_score,
                    q1_score,
                    q1_reasoning,
                    q1_1_score,
                    q1_1_reasoning,
                    q1_2_score,
                    q1_2_reasoning,
                    q2_score,
                    q2_reasoning,
                    q3_score,
                    q3_reasoning,
                    q4_score,
                    q4_reasoning,
                    q4_1_score,
                    q4_1_reasoning,
                    q4_2_score,
                    q4_2_reasoning,
                    q4_3_score,
                    q4_3_reasoning,
                    q4_4_score,
                    q4_4_reasoning,
                    created_at or now,
                    updated_at or now,
                ),
            )
            return annotation_id

    def get_annotations(
        self,
        response_id: Optional[int] = None,
        model: Optional[str] = None,
    ) -> list[Annotation]:
        """Get annotations with optional filters."""
        conditions = []
        params = []

        if response_id:
            conditions.append("response_id = ?")
            params.append(response_id)
        if model:
            conditions.append("model = ?")
            params.append(model)

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        with self._connect() as conn:
            cursor = conn.execute(
                f"SELECT * FROM annotations WHERE {where_clause} ORDER BY response_id",
                params,
            )
            return [Annotation(**dict(row)) for row in cursor.fetchall()]

    # (grade alias, grader_id, output column) for the agreement join.
    _AGREEMENT_GRADERS = [
        ("g_q1", "q1", "q1_score"),
        ("g_q1_1", "q1_1", "q1_1_score"),
        ("g_q1_2", "q1_2", "q1_2_score"),
        ("g_q2", "q2", "q2_score"),
        ("g_q3", "q3", "q3_score"),
        ("g_q4", "q4", "q4_score"),
        ("g_q4_1", "q4_1", "q4_1_score"),
        ("g_q4_2", "q4_2", "q4_2_score"),
        ("g_q4_3", "q4_3", "q4_3_score"),
        ("g_q4_4", "q4_4", "q4_4_score"),
        ("g_pref1", "preference1", "preference1_score"),
        ("g_pref2", "preference2", "preference2_score"),
        ("g_just", "justification", "justification_auto_score"),
    ]

    def get_annotations_with_grades(
        self, valid_only: bool = False, grader_model: Optional[str] = None
    ) -> list[dict]:
        """Get annotations joined with their corresponding grades for agreement analysis.

        Set valid_only to drop annotations whose response_id points at a different
        model's response. The pre-Q1-Q4 annotations were imported with
        response_id = result_uid, which was a per-question index rather than a
        response id, so their joins land on unrelated responses.

        Since grades are keyed on (response_id, grader_id, grader_model), a
        response can carry several grader models' opinions. Each join therefore
        picks exactly one row - the newest, or the newest from grader_model if
        given - so the result stays one row per annotation rather than
        multiplying out and double-counting in the agreement statistics.
        """
        where = (
            "WHERE a.model = r.model"
            if valid_only
            else "WHERE a.preference_score IS NOT NULL OR a.justification_score IS NOT NULL"
            " OR a.q1_score IS NOT NULL OR a.q1_1_score IS NOT NULL"
            " OR a.q1_2_score IS NOT NULL OR a.q2_score IS NOT NULL"
            " OR a.q3_score IS NOT NULL OR a.q4_score IS NOT NULL"
        )
        model_clause = " AND grader_model = ?" if grader_model else ""
        joins = "\n".join(
            f"""LEFT JOIN grades {alias} ON {alias}.id = (
                       SELECT id FROM grades
                       WHERE response_id = a.response_id AND grader_id = '{gid}'{model_clause}
                       ORDER BY created_at DESC, id DESC LIMIT 1)"""
            for alias, gid, _ in self._AGREEMENT_GRADERS
        )
        params = [grader_model] * len(self._AGREEMENT_GRADERS) if grader_model else []

        with self._connect() as conn:
            cursor = conn.execute(
                f"""SELECT
                       a.id as annotation_id,
                       a.response_id,
                       a.model,
                       a.annotator,
                       a.created_at,
                       a.preference_score as human_preference,
                       a.justification_score as human_justification,
                       a.q1_score as human_q1,
                       a.q1_1_score as human_q1_1,
                       a.q1_2_score as human_q1_2,
                       a.q2_score as human_q2,
                       a.q3_score as human_q3,
                       a.q4_score as human_q4,
                       a.q4_1_score as human_q4_1,
                       a.q4_2_score as human_q4_2,
                       a.q4_3_score as human_q4_3,
                       a.q4_4_score as human_q4_4,
                       g_q1.score as q1_score,
                       g_q1_1.score as q1_1_score,
                       g_q1_2.score as q1_2_score,
                       g_q2.score as q2_score,
                       g_q3.score as q3_score,
                       g_q4.score as q4_score,
                       g_q4_1.score as q4_1_score,
                       g_q4_2.score as q4_2_score,
                       g_q4_3.score as q4_3_score,
                       g_q4_4.score as q4_4_score,
                       g_pref1.score as preference1_score,
                       g_pref2.score as preference2_score,
                       g_just.score as justification_auto_score
                   FROM annotations a
                   JOIN responses r ON a.response_id = r.id
                   {joins}
                   {where}
                """,
                params,
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_responses_for_q1q4_annotation(
        self,
        model: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict]:
        """Get responses with their Q1-Q4 LLM grades for the annotation page."""
        conditions = []
        params = []
        
        if model:
            conditions.append("r.model = ?")
            params.append(model)
        
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        params.extend([limit, offset])
        
        with self._connect() as conn:
            cursor = conn.execute(
                f"""SELECT 
                       r.id as response_id,
                       r.model,
                       r.response_text,
                       q.id as question_id,
                       q.topic,
                       q.question_text,
                       g_q1.score as llm_q1_score,
                       g_q1.reasoning as llm_q1_reasoning,
                       g_q2.score as llm_q2_score,
                       g_q2.reasoning as llm_q2_reasoning,
                       g_q3.score as llm_q3_score,
                       g_q3.reasoning as llm_q3_reasoning,
                       g_q4.score as llm_q4_score,
                       g_q4.reasoning as llm_q4_reasoning,
                       a.id as annotation_id,
                       a.q1_score as human_q1_score,
                       a.q1_reasoning as human_q1_reasoning,
                       a.q2_score as human_q2_score,
                       a.q2_reasoning as human_q2_reasoning,
                       a.q3_score as human_q3_score,
                       a.q3_reasoning as human_q3_reasoning,
                       a.q4_score as human_q4_score,
                       a.q4_reasoning as human_q4_reasoning,
                       a.q4_1_score as human_q4_1_score,
                       a.q4_1_reasoning as human_q4_1_reasoning,
                       a.q4_2_score as human_q4_2_score,
                       a.q4_2_reasoning as human_q4_2_reasoning,
                       a.q4_3_score as human_q4_3_score,
                       a.q4_3_reasoning as human_q4_3_reasoning,
                       a.q4_4_score as human_q4_4_score,
                       a.q4_4_reasoning as human_q4_4_reasoning
                   FROM responses r
                   JOIN questions q ON r.question_id = q.id
                   LEFT JOIN grades g_q1 ON g_q1.id = (
                       SELECT id FROM grades WHERE response_id = r.id AND grader_id = 'q1'
                       ORDER BY created_at DESC, id DESC LIMIT 1)
                   LEFT JOIN grades g_q2 ON g_q2.id = (
                       SELECT id FROM grades WHERE response_id = r.id AND grader_id = 'q2'
                       ORDER BY created_at DESC, id DESC LIMIT 1)
                   LEFT JOIN grades g_q3 ON g_q3.id = (
                       SELECT id FROM grades WHERE response_id = r.id AND grader_id = 'q3'
                       ORDER BY created_at DESC, id DESC LIMIT 1)
                   LEFT JOIN grades g_q4 ON g_q4.id = (
                       SELECT id FROM grades WHERE response_id = r.id AND grader_id = 'q4'
                       ORDER BY created_at DESC, id DESC LIMIT 1)
                   LEFT JOIN annotations a ON r.id = a.response_id AND r.model = a.model
                   WHERE {where_clause}
                   ORDER BY r.id
                   LIMIT ? OFFSET ?""",
                params,
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_annotation_by_response_id(self, response_id: int, model: str) -> Optional[Annotation]:
        """Get annotation by response_id and model."""
        with self._connect() as conn:
            cursor = conn.execute(
                "SELECT * FROM annotations WHERE response_id = ? AND model = ?",
                (response_id, model),
            )
            row = cursor.fetchone()
            return Annotation(**dict(row)) if row else None

    # Utility operations

    def get_grader_version(self) -> str:
        """Git hash of the last commit that touched the grader prompts."""
        try:
            result = subprocess.run(
                ["git", "log", "-1", "--format=%h", "--",
                 "prompts/graders", "src/aestheticbench/benchmark/prompts.py"],
                capture_output=True,
                text=True,
                cwd=self.db_path.parent,
            )
            return result.stdout.strip() or "unknown"
        except Exception:
            return "unknown"

    def get_models(self) -> list[str]:
        """Get list of all models that have responses."""
        with self._connect() as conn:
            cursor = conn.execute(
                "SELECT DISTINCT model FROM responses ORDER BY model"
            )
            return [row["model"] for row in cursor.fetchall()]

    def get_topics(self) -> list[str]:
        """Get list of all topics."""
        with self._connect() as conn:
            cursor = conn.execute(
                "SELECT DISTINCT topic FROM questions ORDER BY topic"
            )
            return [row["topic"] for row in cursor.fetchall()]

    def get_stats(self) -> dict:
        """Get database statistics."""
        with self._connect() as conn:
            questions = conn.execute("SELECT COUNT(*) as c FROM questions").fetchone()["c"]
            responses = conn.execute("SELECT COUNT(*) as c FROM responses").fetchone()["c"]
            grades = conn.execute("SELECT COUNT(*) as c FROM grades").fetchone()["c"]
            models = conn.execute("SELECT COUNT(DISTINCT model) as c FROM responses").fetchone()["c"]
            return {
                "questions": questions,
                "responses": responses,
                "grades": grades,
                "models": models,
            }

    # Export operations

    def export_responses_csv(
        self,
        output_path: str | Path,
        model: Optional[str] = None,
        run_index: Optional[int] = None,
    ) -> int:
        """Export responses to CSV. Returns row count."""
        conditions = []
        params = []
        
        if model:
            conditions.append("r.model = ?")
            params.append(model)
        if run_index:
            conditions.append("r.run_index = ?")
            params.append(run_index)

        where_clause = " AND ".join(conditions) if conditions else "1=1"
        
        with self._connect() as conn:
            cursor = conn.execute(
                f"""SELECT q.topic, q.question_text, r.model, r.response_text, 
                           r.run_index, r.created_at
                    FROM responses r
                    JOIN questions q ON r.question_id = q.id
                    WHERE {where_clause}
                    ORDER BY r.model, q.id, r.run_index""",
                params,
            )
            rows = cursor.fetchall()

        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Topic", "Question", "Model", "Response", "Run Index", "Timestamp"])
            for row in rows:
                writer.writerow([
                    row["topic"],
                    row["question_text"],
                    row["model"],
                    row["response_text"],
                    row["run_index"],
                    row["created_at"],
                ])
        return len(rows)

    def export_grades_csv(
        self,
        output_path: str | Path,
        model: Optional[str] = None,
        grader_id: Optional[str] = None,
    ) -> int:
        """Export grades to CSV. Returns row count."""
        conditions = []
        params = []
        
        if model:
            conditions.append("r.model = ?")
            params.append(model)
        if grader_id:
            conditions.append("g.grader_id = ?")
            params.append(grader_id)

        where_clause = " AND ".join(conditions) if conditions else "1=1"
        
        with self._connect() as conn:
            cursor = conn.execute(
                f"""SELECT q.topic, q.question_text, r.model, r.response_text,
                           r.run_index, g.grader_id, g.score, g.reasoning, 
                           g.grader_version, g.created_at
                    FROM grades g
                    JOIN responses r ON g.response_id = r.id
                    JOIN questions q ON r.question_id = q.id
                    WHERE {where_clause}
                    ORDER BY r.model, q.id, r.run_index, g.grader_id""",
                params,
            )
            rows = cursor.fetchall()

        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "Topic", "Question", "Model", "Response", "Run Index",
                "Grader", "Score", "Reasoning", "Grader Version", "Timestamp"
            ])
            for row in rows:
                writer.writerow([
                    row["topic"],
                    row["question_text"],
                    row["model"],
                    row["response_text"],
                    row["run_index"],
                    row["grader_id"],
                    row["score"],
                    row["reasoning"],
                    row["grader_version"],
                    row["created_at"],
                ])
        return len(rows)

    # Migration from existing CSVs

    def migrate_from_csv_dir(self, results_dir: str | Path) -> dict:
        """Migrate existing CSV results into the database."""
        results_dir = Path(results_dir)
        stats = {"questions": 0, "responses": 0, "grades": 0, "files": 0}
        
        # Import from responses directory
        responses_dir = results_dir / "responses"
        if responses_dir.exists():
            for csv_file in responses_dir.glob("*.csv"):
                self._import_response_csv(csv_file)
                stats["files"] += 1

        # Import from grades directory
        grades_dir = results_dir / "grades"
        if grades_dir.exists():
            for csv_file in grades_dir.glob("*.csv"):
                self._import_graded_csv(csv_file)
                stats["files"] += 1

        db_stats = self.get_stats()
        stats["questions"] = db_stats["questions"]
        stats["responses"] = db_stats["responses"]
        stats["grades"] = db_stats["grades"]
        return stats

    def _import_response_csv(self, csv_file: Path):
        """Import a single response CSV file."""
        # Extract model from filename: {provider}_{model}_{date}_{time}.csv
        parts = csv_file.stem.rsplit("_", 2)
        model_name = parts[0].replace("_", "/", 1) if len(parts) >= 3 else csv_file.stem
        
        with open(csv_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                topic = row.get("Topic", "")
                question = row.get("Question", "")
                response = row.get("Model Response", "")
                
                if question and response:
                    q_id = self.add_question(topic, question)
                    self.add_response(q_id, model_name, response)

    def _import_graded_csv(self, csv_file: Path):
        """Import a single graded CSV file."""
        # Extract model from filename
        parts = csv_file.stem.split("_graded_")[0].rsplit("_", 2)
        model_name = parts[0].replace("_", "/", 1) if len(parts) >= 3 else parts[0]
        
        # Mapping from CSV column prefixes to canonical grader IDs
        grader_id_map = {
            "q1_relativism": "q1",
            "q2_preference": "q2",
            "q3_evidence": "q3",
            "q4_justification": "q4",
            "preference_1": "preference1",
            "preference_2": "preference2",
            "justification": "justification",
            "relativism": "relativism",
            "whimsical": "whimsical",
            "factual_depth": "factual_depth",
            "custom": "custom",
        }
        
        with open(csv_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames or []
            
            # Find grade columns (ending with _Score)
            grade_cols = {}
            for h in headers:
                if h.endswith("_Score"):
                    raw_grader_id = h.rsplit("_Score", 1)[0].lower()
                    # Normalize grader ID
                    grader_id = grader_id_map.get(raw_grader_id, raw_grader_id)
                    reasoning_col = h.rsplit("_Score", 1)[0] + "_Reasoning"
                    grade_cols[grader_id] = (h, reasoning_col if reasoning_col in headers else None)
            
            for row in reader:
                topic = row.get("Topic", "")
                question = row.get("Question", "")
                response = row.get("Model Response", "")
                
                if not question or not response:
                    continue
                
                q_id = self.add_question(topic, question)
                r_id = self.add_response(q_id, model_name, response)
                
                for grader_id, (score_col, reasoning_col) in grade_cols.items():
                    score = row.get(score_col, "")
                    if score and not score.startswith("ERROR") and not score.startswith("PARSE_ERROR"):
                        reasoning = row.get(reasoning_col, "") if reasoning_col else None
                        self.add_grade(r_id, grader_id, score, reasoning)
