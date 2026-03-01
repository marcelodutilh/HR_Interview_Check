import json
import os
from flask import Flask, render_template, request, redirect, url_for, abort, jsonify, Response, stream_with_context
from database import get_db, init_db, get_setting, set_setting
from ai import analyse_interview, build_chat_system


def get_anthropic_api_key():
    """Return API key from environment or from stored settings."""
    return os.environ.get("ANTHROPIC_API_KEY") or get_setting("anthropic_api_key")

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-please-set-in-production")


def normalise_competencies(raw):
    """
    Accept either a JSON string or already-parsed value.
    Old format: ["Communication", "Problem Solving"]
    New format: [{"name": "...", "strong": "...", "acceptable": "...", "weak": "..."}]
    Always returns a list of dicts in the new format.
    """
    if isinstance(raw, str):
        try:
            data = json.loads(raw)
        except (ValueError, TypeError):
            return []
    else:
        data = raw
    if not isinstance(data, list):
        return []
    result = []
    for item in data:
        if isinstance(item, str):
            result.append({"name": item, "strong": "", "acceptable": "", "weak": ""})
        elif isinstance(item, dict):
            result.append({
                "name":       str(item.get("name", "")),
                "strong":     str(item.get("strong", "")),
                "acceptable": str(item.get("acceptable", "")),
                "weak":       str(item.get("weak", "")),
            })
    return result


@app.before_request
def ensure_db():
    pass  # DB is initialised once at startup


# ---------------------------------------------------------------------------
# Job Searches
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    conn = get_db()
    searches = conn.execute("""
        SELECT js.*, COUNT(c.id) AS candidate_count
        FROM job_searches js
        LEFT JOIN candidates c ON c.job_search_id = js.id
        GROUP BY js.id
        ORDER BY js.created_at DESC
    """).fetchall()
    conn.close()
    return render_template("index.html", searches=searches)


@app.route("/job-searches/new", methods=["GET", "POST"])
def job_search_new():
    if request.method == "POST":
        title = request.form["title"].strip()
        description = request.form.get("description", "").strip()
        if not title:
            return render_template("job_searches/form.html", error="Title is required.", values=request.form)
        conn = get_db()
        cur = conn.execute(
            "INSERT INTO job_searches (title, description) VALUES (?, ?)",
            (title, description),
        )
        conn.commit()
        new_id = cur.lastrowid
        conn.close()
        return redirect(url_for("job_search_detail", search_id=new_id))
    return render_template("job_searches/form.html", values={})


@app.route("/job-searches/<int:search_id>")
def job_search_detail(search_id):
    conn = get_db()
    search = conn.execute(
        "SELECT * FROM job_searches WHERE id = ?", (search_id,)
    ).fetchone()
    if not search:
        abort(404)
    candidates = conn.execute(
        "SELECT * FROM candidates WHERE job_search_id = ? ORDER BY created_at DESC",
        (search_id,),
    ).fetchall()
    rubric = conn.execute(
        "SELECT * FROM rubrics WHERE job_search_id = ? ORDER BY created_at DESC LIMIT 1",
        (search_id,),
    ).fetchone()
    conn.close()
    competencies = normalise_competencies(rubric["competencies"]) if rubric else []
    return render_template(
        "job_searches/detail.html",
        search=search,
        candidates=candidates,
        rubric=rubric,
        competencies=competencies,
    )


@app.route("/job-searches/<int:search_id>/edit", methods=["GET", "POST"])
def job_search_edit(search_id):
    conn = get_db()
    search = conn.execute(
        "SELECT * FROM job_searches WHERE id = ?", (search_id,)
    ).fetchone()
    if not search:
        abort(404)
    if request.method == "POST":
        title = request.form["title"].strip()
        description = request.form.get("description", "").strip()
        if not title:
            return render_template("job_searches/form.html", error="Title is required.", values=request.form, search=search)
        conn.execute(
            "UPDATE job_searches SET title = ?, description = ? WHERE id = ?",
            (title, description, search_id),
        )
        conn.commit()
        conn.close()
        return redirect(url_for("job_search_detail", search_id=search_id))
    conn.close()
    return render_template("job_searches/form.html", values=search, search=search)


@app.route("/job-searches/<int:search_id>/delete", methods=["POST"])
def job_search_delete(search_id):
    conn = get_db()
    conn.execute("DELETE FROM job_searches WHERE id = ?", (search_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("index"))


# ---------------------------------------------------------------------------
# Rubrics
# ---------------------------------------------------------------------------

@app.route("/job-searches/<int:search_id>/rubric", methods=["GET", "POST"])
def rubric_edit(search_id):
    conn = get_db()
    search = conn.execute(
        "SELECT * FROM job_searches WHERE id = ?", (search_id,)
    ).fetchone()
    if not search:
        abort(404)
    rubric = conn.execute(
        "SELECT * FROM rubrics WHERE job_search_id = ? ORDER BY created_at DESC LIMIT 1",
        (search_id,),
    ).fetchone()

    if request.method == "POST":
        raw = request.form.get("competencies", "[]")
        try:
            parsed = json.loads(raw)
            if not isinstance(parsed, list):
                raise ValueError
        except (ValueError, json.JSONDecodeError):
            conn.close()
            competencies = normalise_competencies(rubric["competencies"]) if rubric else []
            return render_template(
                "rubrics/form.html",
                search=search,
                rubric=rubric,
                competencies=competencies,
                error="Invalid data — could not save rubric.",
            )
        competencies = [c for c in normalise_competencies(parsed) if c["name"].strip()]
        serialised = json.dumps(competencies)
        if rubric:
            conn.execute(
                "UPDATE rubrics SET competencies = ? WHERE id = ?",
                (serialised, rubric["id"]),
            )
        else:
            conn.execute(
                "INSERT INTO rubrics (job_search_id, competencies) VALUES (?, ?)",
                (search_id, serialised),
            )
        conn.commit()
        conn.close()
        return redirect(url_for("job_search_detail", search_id=search_id))

    conn.close()
    competencies = normalise_competencies(rubric["competencies"]) if rubric else []
    return render_template(
        "rubrics/form.html",
        search=search,
        rubric=rubric,
        competencies=competencies,
        raw=json.dumps(competencies),
    )


# ---------------------------------------------------------------------------
# Candidates
# ---------------------------------------------------------------------------

@app.route("/job-searches/<int:search_id>/candidates/new", methods=["GET", "POST"])
def candidate_new(search_id):
    conn = get_db()
    search = conn.execute(
        "SELECT * FROM job_searches WHERE id = ?", (search_id,)
    ).fetchone()
    if not search:
        abort(404)
    if request.method == "POST":
        name = request.form["name"].strip()
        notes = request.form.get("notes", "").strip()
        if not name:
            conn.close()
            return render_template("candidates/form.html", search=search, error="Name is required.", values=request.form)
        cur = conn.execute(
            "INSERT INTO candidates (job_search_id, name, notes) VALUES (?, ?, ?)",
            (search_id, name, notes),
        )
        conn.commit()
        new_id = cur.lastrowid
        conn.close()
        return redirect(url_for("candidate_detail", candidate_id=new_id))
    conn.close()
    return render_template("candidates/form.html", search=search, values={})


@app.route("/candidates/<int:candidate_id>")
def candidate_detail(candidate_id):
    conn = get_db()
    candidate = conn.execute(
        "SELECT * FROM candidates WHERE id = ?", (candidate_id,)
    ).fetchone()
    if not candidate:
        abort(404)
    search = conn.execute(
        "SELECT * FROM job_searches WHERE id = ?", (candidate["job_search_id"],)
    ).fetchone()
    interviews = conn.execute(
        "SELECT * FROM interviews WHERE candidate_id = ? ORDER BY created_at DESC",
        (candidate_id,),
    ).fetchall()
    rubric = conn.execute(
        "SELECT * FROM rubrics WHERE job_search_id = ? ORDER BY created_at DESC LIMIT 1",
        (candidate["job_search_id"],),
    ).fetchone()
    conn.close()
    competencies = normalise_competencies(rubric["competencies"]) if rubric else []
    return render_template(
        "candidates/detail.html",
        candidate=candidate,
        search=search,
        interviews=interviews,
        competencies=competencies,
    )


@app.route("/candidates/<int:candidate_id>/edit", methods=["GET", "POST"])
def candidate_edit(candidate_id):
    conn = get_db()
    candidate = conn.execute(
        "SELECT * FROM candidates WHERE id = ?", (candidate_id,)
    ).fetchone()
    if not candidate:
        abort(404)
    search = conn.execute(
        "SELECT * FROM job_searches WHERE id = ?", (candidate["job_search_id"],)
    ).fetchone()
    if request.method == "POST":
        name = request.form["name"].strip()
        notes = request.form.get("notes", "").strip()
        if not name:
            conn.close()
            return render_template("candidates/form.html", search=search, candidate=candidate, error="Name is required.", values=request.form)
        conn.execute(
            "UPDATE candidates SET name = ?, notes = ? WHERE id = ?",
            (name, notes, candidate_id),
        )
        conn.commit()
        conn.close()
        return redirect(url_for("candidate_detail", candidate_id=candidate_id))
    conn.close()
    return render_template("candidates/form.html", search=search, candidate=candidate, values=candidate)


@app.route("/candidates/<int:candidate_id>/delete", methods=["POST"])
def candidate_delete(candidate_id):
    conn = get_db()
    candidate = conn.execute(
        "SELECT job_search_id FROM candidates WHERE id = ?", (candidate_id,)
    ).fetchone()
    if not candidate:
        abort(404)
    search_id = candidate["job_search_id"]
    conn.execute("DELETE FROM candidates WHERE id = ?", (candidate_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("job_search_detail", search_id=search_id))


# ---------------------------------------------------------------------------
# Interviews
# ---------------------------------------------------------------------------

@app.route("/candidates/<int:candidate_id>/interviews/new", methods=["GET", "POST"])
def interview_new(candidate_id):
    conn = get_db()
    candidate = conn.execute(
        "SELECT * FROM candidates WHERE id = ?", (candidate_id,)
    ).fetchone()
    if not candidate:
        abort(404)
    search = conn.execute(
        "SELECT * FROM job_searches WHERE id = ?", (candidate["job_search_id"],)
    ).fetchone()
    rubric = conn.execute(
        "SELECT * FROM rubrics WHERE job_search_id = ? ORDER BY created_at DESC LIMIT 1",
        (candidate["job_search_id"],),
    ).fetchone()
    competencies = normalise_competencies(rubric["competencies"]) if rubric else []

    ai_enabled = bool(get_anthropic_api_key())

    if request.method == "POST":
        transcript = request.form.get("transcript", "").strip()
        ai_analysis_json = None
        analysis_error = None

        if transcript and ai_enabled:
            try:
                result = analyse_interview(
                    candidate_name=candidate["name"],
                    job_title=search["title"],
                    competencies=competencies,
                    transcript=transcript,
                    api_key=get_anthropic_api_key(),
                )
                ai_analysis_json = json.dumps(result)
            except Exception as exc:
                analysis_error = str(exc)

        cur = conn.execute(
            "INSERT INTO interviews (candidate_id, transcript, ai_analysis) VALUES (?, ?, ?)",
            (candidate_id, transcript, ai_analysis_json),
        )
        conn.commit()
        new_id = cur.lastrowid
        conn.close()
        return redirect(url_for(
            "interview_detail",
            interview_id=new_id,
            analysis_error=analysis_error or "",
        ))

    conn.close()
    return render_template(
        "interviews/form.html",
        candidate=candidate,
        search=search,
        competencies=competencies,
        ai_enabled=ai_enabled,
        values={},
    )


@app.route("/interviews/<int:interview_id>")
def interview_detail(interview_id):
    conn = get_db()
    interview = conn.execute(
        "SELECT * FROM interviews WHERE id = ?", (interview_id,)
    ).fetchone()
    if not interview:
        abort(404)
    candidate = conn.execute(
        "SELECT * FROM candidates WHERE id = ?", (interview["candidate_id"],)
    ).fetchone()
    search = conn.execute(
        "SELECT * FROM job_searches WHERE id = ?", (candidate["job_search_id"],)
    ).fetchone()
    rubric = conn.execute(
        "SELECT * FROM rubrics WHERE job_search_id = ? ORDER BY created_at DESC LIMIT 1",
        (candidate["job_search_id"],),
    ).fetchone()
    conn.close()
    competencies = normalise_competencies(rubric["competencies"]) if rubric else []
    ai_analysis = None
    if interview["ai_analysis"]:
        try:
            ai_analysis = json.loads(interview["ai_analysis"])
        except (ValueError, json.JSONDecodeError):
            ai_analysis = {"_raw": interview["ai_analysis"]}
    return render_template(
        "interviews/detail.html",
        interview=interview,
        candidate=candidate,
        search=search,
        competencies=competencies,
        ai_analysis=ai_analysis,
        ai_enabled=bool(get_anthropic_api_key()),
        analysis_error=request.args.get("analysis_error", ""),
    )


@app.route("/interviews/<int:interview_id>/edit", methods=["GET", "POST"])
def interview_edit(interview_id):
    conn = get_db()
    interview = conn.execute(
        "SELECT * FROM interviews WHERE id = ?", (interview_id,)
    ).fetchone()
    if not interview:
        abort(404)
    candidate = conn.execute(
        "SELECT * FROM candidates WHERE id = ?", (interview["candidate_id"],)
    ).fetchone()
    search = conn.execute(
        "SELECT * FROM job_searches WHERE id = ?", (candidate["job_search_id"],)
    ).fetchone()
    rubric = conn.execute(
        "SELECT * FROM rubrics WHERE job_search_id = ? ORDER BY created_at DESC LIMIT 1",
        (candidate["job_search_id"],),
    ).fetchone()
    competencies = normalise_competencies(rubric["competencies"]) if rubric else []

    if request.method == "POST":
        transcript = request.form.get("transcript", "").strip()
        conn.execute(
            "UPDATE interviews SET transcript = ? WHERE id = ?",
            (transcript, interview_id),
        )
        conn.commit()
        conn.close()
        return redirect(url_for("interview_detail", interview_id=interview_id))
    conn.close()
    return render_template(
        "interviews/form.html",
        candidate=candidate,
        search=search,
        interview=interview,
        competencies=competencies,
        ai_enabled=bool(get_anthropic_api_key()),
        values=interview,
    )


@app.route("/interviews/<int:interview_id>/analyse", methods=["POST"])
def interview_analyse(interview_id):
    """Re-run AI analysis on an existing interview transcript."""
    if not get_anthropic_api_key():
        return jsonify({"error": "No API key. Add one in Settings."}), 503

    conn = get_db()
    interview = conn.execute(
        "SELECT * FROM interviews WHERE id = ?", (interview_id,)
    ).fetchone()
    if not interview:
        conn.close()
        return jsonify({"error": "Interview not found."}), 404

    if not interview["transcript"]:
        conn.close()
        return jsonify({"error": "No transcript to analyse."}), 400

    candidate = conn.execute(
        "SELECT * FROM candidates WHERE id = ?", (interview["candidate_id"],)
    ).fetchone()
    search = conn.execute(
        "SELECT * FROM job_searches WHERE id = ?", (candidate["job_search_id"],)
    ).fetchone()
    rubric = conn.execute(
        "SELECT * FROM rubrics WHERE job_search_id = ? ORDER BY created_at DESC LIMIT 1",
        (candidate["job_search_id"],),
    ).fetchone()
    competencies = normalise_competencies(rubric["competencies"]) if rubric else []

    try:
        result = analyse_interview(
            candidate_name=candidate["name"],
            job_title=search["title"],
            competencies=competencies,
            transcript=interview["transcript"],
            api_key=get_anthropic_api_key(),
        )
        conn.execute(
            "UPDATE interviews SET ai_analysis = ? WHERE id = ?",
            (json.dumps(result), interview_id),
        )
        conn.commit()
        conn.close()
        return jsonify({"ok": True, "analysis": result})
    except Exception as exc:
        conn.close()
        return jsonify({"error": str(exc)}), 500


@app.route("/interviews/<int:interview_id>/chat", methods=["POST"])
def interview_chat(interview_id):
    """Stream a conversational follow-up response about this interview."""
    api_key = get_anthropic_api_key()
    if not api_key:
        return jsonify({"error": "No API key. Add one in Settings."}), 503

    conn = get_db()
    interview = conn.execute(
        "SELECT * FROM interviews WHERE id = ?", (interview_id,)
    ).fetchone()
    if not interview:
        conn.close()
        return jsonify({"error": "Interview not found."}), 404

    candidate = conn.execute(
        "SELECT * FROM candidates WHERE id = ?", (interview["candidate_id"],)
    ).fetchone()
    search = conn.execute(
        "SELECT * FROM job_searches WHERE id = ?", (candidate["job_search_id"],)
    ).fetchone()
    conn.close()

    data = request.get_json(silent=True) or {}
    question = (data.get("question") or "").strip()
    if not question:
        return jsonify({"error": "Question is required."}), 400

    # Sanitise and cap history to prevent context bloat
    raw_history = data.get("history") or []
    history = []
    for h in raw_history:
        if isinstance(h, dict) and h.get("role") in ("user", "assistant") and h.get("content"):
            history.append({"role": h["role"], "content": str(h["content"])[:8000]})

    messages = history + [{"role": "user", "content": question}]
    system_prompt = build_chat_system(
        candidate_name=candidate["name"],
        job_title=search["title"],
        transcript=interview["transcript"],
        ai_analysis_json=interview["ai_analysis"],
    )

    import anthropic as _anthropic

    def generate():
        client = _anthropic.Anthropic(api_key=api_key)
        try:
            with client.messages.stream(
                model="claude-sonnet-4-6",
                max_tokens=1024,
                system=system_prompt,
                messages=messages,
            ) as stream:
                for text in stream.text_stream:
                    yield "data: " + json.dumps({"type": "text", "text": text}) + "\n\n"
                yield "data: " + json.dumps({"type": "done"}) + "\n\n"
        except Exception as exc:
            yield "data: " + json.dumps({"type": "error", "error": str(exc)}) + "\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.route("/interviews/<int:interview_id>/delete", methods=["POST"])
def interview_delete(interview_id):
    conn = get_db()
    interview = conn.execute(
        "SELECT candidate_id FROM interviews WHERE id = ?", (interview_id,)
    ).fetchone()
    if not interview:
        abort(404)
    candidate_id = interview["candidate_id"]
    conn.execute("DELETE FROM interviews WHERE id = ?", (interview_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("candidate_detail", candidate_id=candidate_id))


# ---------------------------------------------------------------------------
# Settings (API key)
# ---------------------------------------------------------------------------

@app.route("/settings", methods=["GET", "POST"])
def settings():
    if request.method == "POST":
        key = (request.form.get("anthropic_api_key") or "").strip()
        if key:
            set_setting("anthropic_api_key", key)
            return redirect(url_for("settings") + "?saved=1")
        else:
            set_setting("anthropic_api_key", "")
            return redirect(url_for("settings") + "?cleared=1")
    stored = get_setting("anthropic_api_key")
    return render_template(
        "settings.html",
        has_key=bool(stored),
        saved=request.args.get("saved"),
        cleared=request.args.get("cleared"),
    )


# ---------------------------------------------------------------------------
# JSON API
# ---------------------------------------------------------------------------

@app.route("/api/job-searches", methods=["GET"])
def api_job_searches():
    conn = get_db()
    rows = conn.execute("""
        SELECT js.*, COUNT(c.id) AS candidate_count
        FROM job_searches js
        LEFT JOIN candidates c ON c.job_search_id = js.id
        GROUP BY js.id
        ORDER BY js.created_at DESC
    """).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route("/api/job-searches", methods=["POST"])
def api_job_search_create():
    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "").strip()
    description = (data.get("description") or "").strip()
    if not title:
        return jsonify({"error": "Title is required."}), 400
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO job_searches (title, description) VALUES (?, ?)",
        (title, description),
    )
    conn.commit()
    row = conn.execute(
        "SELECT *, 0 AS candidate_count FROM job_searches WHERE id = ?", (cur.lastrowid,)
    ).fetchone()
    conn.close()
    return jsonify(dict(row)), 201


@app.route("/api/job-searches/<int:search_id>/candidates", methods=["GET"])
def api_candidates(search_id):
    conn = get_db()
    rows = conn.execute(
        "SELECT id, name, notes, created_at FROM candidates WHERE job_search_id = ? ORDER BY created_at DESC",
        (search_id,),
    ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route("/api/job-searches/<int:search_id>/candidates", methods=["POST"])
def api_candidate_create(search_id):
    conn = get_db()
    search = conn.execute(
        "SELECT id FROM job_searches WHERE id = ?", (search_id,)
    ).fetchone()
    if not search:
        conn.close()
        return jsonify({"error": "Job search not found."}), 404
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    notes = (data.get("notes") or "").strip()
    if not name:
        conn.close()
        return jsonify({"error": "Name is required."}), 400
    cur = conn.execute(
        "INSERT INTO candidates (job_search_id, name, notes) VALUES (?, ?, ?)",
        (search_id, name, notes),
    )
    conn.commit()
    row = conn.execute(
        "SELECT * FROM candidates WHERE id = ?", (cur.lastrowid,)
    ).fetchone()
    conn.close()
    return jsonify(dict(row)), 201


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    init_db()
    app.run(debug=True, threaded=True)
