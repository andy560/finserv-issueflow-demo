"""
IssueFlow - Two-Stage Autonomous Issue Resolution via Devin API
===============================================================
Stage 1 (Scope): Devin reads the issue, explores the codebase,
                 and produces a structured report — no code written.
Stage 2 (Fix):   Triggered after human approval. Devin implements
                 the fix, runs tests, and opens a PR with a plain-
                 English summary.

Setup:
    pip install requests flask flask-cors python-dotenv

    Create a .env file in the same folder with:
        GITHUB_TOKEN=ghp_...
        DEVIN_API_KEY=cog_...
        DEVIN_ORG_ID=org_...

Usage:
    python process_issues.py --scan          # Stage 1: scope all open issues
    python process_issues.py --issue 3       # Stage 1: scope a single issue
    python process_issues.py --serve         # Run API server for dashboard
    python process_issues.py --approve 3 --mode autofix
    python process_issues.py --approve 3 --mode review
    python process_issues.py --rollback 3
    python process_issues.py --scan --dry-run
"""

import argparse
import json
import os
import time
import threading
from datetime import datetime
from pathlib import Path

import requests

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    from flask import Flask, jsonify, request as flask_request
    from flask_cors import CORS
    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False

# ============================================================
# CONFIGURATION — loaded from .env file, never hardcoded
# ============================================================

GITHUB_TOKEN  = os.environ.get("GITHUB_TOKEN", "")
GITHUB_REPO   = "andy560/finserv-issueflow-demo"

DEVIN_API_KEY = os.environ.get("DEVIN_API_KEY", "")
DEVIN_ORG_ID  = os.environ.get("DEVIN_ORG_ID", "")

STATE_FILE = Path("issueflow_state.json")

def check_config():
    missing = []
    if not GITHUB_TOKEN:  missing.append("GITHUB_TOKEN")
    if not DEVIN_API_KEY: missing.append("DEVIN_API_KEY")
    if not DEVIN_ORG_ID:  missing.append("DEVIN_ORG_ID")
    if missing:
        print(f"❌ Missing environment variables: {', '.join(missing)}")
        print(f"   Create a .env file with these values. See README for details.")
        raise SystemExit(1)

# ============================================================
# STATE
# ============================================================

def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"issues": {}, "audit_log": []}

def save_state(state):
    STATE_FILE.write_text(json.dumps(state, indent=2))

def log_audit(state, action, issue_number, detail="", actor="IssueFlow"):
    state["audit_log"].insert(0, {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "actor":     actor,
        "action":    action,
        "issue":     str(issue_number),
        "detail":    detail
    })
    state["audit_log"] = state["audit_log"][:200]

# ============================================================
# GITHUB
# ============================================================

def gh_headers():
    return {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json"
    }

def get_all_open_issues():
    r = requests.get(
        f"https://api.github.com/repos/{GITHUB_REPO}/issues",
        headers=gh_headers(),
        params={"state": "open", "per_page": 50}
    )
    r.raise_for_status()
    return [i for i in r.json() if "pull_request" not in i]

def get_single_issue(number):
    r = requests.get(
        f"https://api.github.com/repos/{GITHUB_REPO}/issues/{number}",
        headers=gh_headers()
    )
    r.raise_for_status()
    return r.json()

def post_github_comment(number, body):
    r = requests.post(
        f"https://api.github.com/repos/{GITHUB_REPO}/issues/{number}/comments",
        headers=gh_headers(),
        json={"body": body}
    )
    r.raise_for_status()

def close_pr_and_reopen_issue(pr_number, issue_number):
    requests.patch(
        f"https://api.github.com/repos/{GITHUB_REPO}/pulls/{pr_number}",
        headers=gh_headers(),
        json={"state": "closed"}
    )
    requests.patch(
        f"https://api.github.com/repos/{GITHUB_REPO}/issues/{issue_number}",
        headers=gh_headers(),
        json={"state": "open"}
    )

# ============================================================
# CLASSIFICATION
# ============================================================

RISKY_KEYWORDS = [
    "database", "migration", "schema", "production", "security",
    "auth token", "payment", "deploy", "infrastructure", "refactor",
    "breaking change", "architecture", "credentials", "encryption"
]

def classify_issue(issue):
    text = (issue["title"] + " " + (issue["body"] or "")).lower()
    risk_flags = [kw for kw in RISKY_KEYWORDS if kw in text]
    body_length = len(issue["body"] or "")
    safe = len(risk_flags) == 0 and body_length < 600
    return {
        "safe_for_autofix": safe,
        "risk_flags": risk_flags,
        "complexity": "low" if body_length < 200 else "medium",
        "reason": "No risk flags detected" if safe else f"Risk flags: {', '.join(risk_flags)}"
    }

def _guess_file(issue):
    title = issue["title"].lower()
    if any(k in title for k in ["divide", "interest", "discount", "calculator"]):
        return "calculator.py"
    if any(k in title for k in ["email", "mask", "account", "auth", "password"]):
        return "auth.py"
    if any(k in title for k in ["currency", "format", "truncate", "date", "utils"]):
        return "utils.py"
    return "unknown"

# ============================================================
# DEVIN
# ============================================================

def devin_post(endpoint, payload):
    url = f"https://api.devin.ai/v3/organizations/{DEVIN_ORG_ID}/{endpoint}"
    r = requests.post(url, headers={
        "Authorization": f"Bearer {DEVIN_API_KEY}",
        "Content-Type": "application/json"
    }, json=payload)
    r.raise_for_status()
    return r.json()

def devin_get_session(session_id):
    url = f"https://api.devin.ai/v3/organizations/{DEVIN_ORG_ID}/sessions/{session_id}"
    r = requests.get(url, headers={"Authorization": f"Bearer {DEVIN_API_KEY}"})
    r.raise_for_status()
    return r.json()

# ============================================================
# STAGE 1 PROMPT — scope only, no code
# ============================================================

def build_scope_prompt(issue):
    return f"""You are performing a SCOPING ANALYSIS ONLY. DO NOT write any code, create branches, or make any changes to the repository.

Repository: {GITHUB_REPO}
Issue #{issue['number']}: {issue['title']}

{issue['body'] or 'No description provided.'}

Explore the repository and produce a structured scoping report using EXACTLY this format:

## Root Cause
[One or two sentences: where and why the bug occurs. Include file name and line number.]

## Proposed Fix
[One or two sentences: the minimal code change needed. Be specific — function name and logic to add.]

## Files Affected
[List only the files that need to change.]

## Test Coverage
[Which existing test(s) will verify the fix? Confirm they currently fail.]

## Risk Assessment
[LOW / MEDIUM / HIGH — one sentence of reasoning.]

## Estimated Fix Time
[Your estimate in minutes.]

Be concise. Do not write any code. Do not make any commits or file changes.
"""

# ============================================================
# STAGE 2 PROMPT — implement fix
# ============================================================

def build_fix_prompt(issue, scope_report, mode):
    review_note = ""
    if mode == "review":
        review_note = "\nIMPORTANT: In the PR description, explicitly request a human code review before merging."

    return f"""You are fixing a bug in the GitHub repository: {GITHUB_REPO}

Issue #{issue['number']}: {issue['title']}

A scoping report was reviewed and approved by the engineering team:

{scope_report}

## Instructions

1. Create a new branch: fix/issue-{issue['number']}
2. Implement ONLY the fix described in the scoping report.
3. Run: pytest
4. All tests must pass. Do NOT modify any test files.
5. Commit: "fix: resolve issue #{issue['number']} - {issue['title']}"
6. Push branch and open a pull request referencing issue #{issue['number']}.
7. Once the pull request is open, post a comment on GitHub issue #{issue['number']} in repository {GITHUB_REPO} with this exact text:
   IssueFlow: PR opened — [paste the full PR URL here]

## PR Description — write it like a real engineer, plain English, under 150 words:
- What was broken and why (one sentence)
- What you changed (one sentence, specific — include function name)
- How to verify (name the test)
- Any edge cases considered
{review_note}

Only change files listed in the scoping report. Nothing else.
"""

# ============================================================
# DISPATCH SCOPE SESSION
# ============================================================

def dispatch_scope_session(issue, dry_run=False):
    state = load_state()
    num = str(issue["number"])
    classification = classify_issue(issue)

    print(f"\n{'='*55}")
    print(f"Issue #{num}: {issue['title']}")

    if not classification["safe_for_autofix"]:
        print(f"⏭  Skipped — {classification['reason']}")
        return

    print(f"🔍 Dispatching Stage 1 scope session...")

    if dry_run:
        session_id = f"dry-run-scope-{num}"
        print(f"   [DRY RUN] Would create scope session.")
    else:
        result = devin_post("sessions", {"prompt": build_scope_prompt(issue)})
        session_id = result.get("session_id") or result.get("id")
        post_github_comment(issue["number"],
            f"🔍 **IssueFlow Stage 1 — Scoping:** Devin is analyzing this issue.\n\n"
            f"No code will be written until an engineer reviews and approves the scoping report.\n\n"
            f"Devin session: https://app.devin.ai/sessions/{session_id}"
        )

    state["issues"][num] = {
        "number":           issue["number"],
        "title":            issue["title"],
        "body":             issue["body"] or "",
        "html_url":         issue.get("html_url", ""),
        "file":             _guess_file(issue),
        "status":           "scoping",
        "classification":   classification,
        "scope_session_id": session_id,
        "scope_report":     None,
        "fix_session_id":   None,
        "pr_number":        None,
        "pr_url":           None,
        "decision":         None,
        "created_at":       datetime.utcnow().isoformat() + "Z",
        "updated_at":       datetime.utcnow().isoformat() + "Z",
    }
    log_audit(state, "scope_dispatched", num, f"Session: {session_id}")
    save_state(state)
    print(f"   ✅ https://app.devin.ai/sessions/{session_id}")

# ============================================================
# APPROVE
# ============================================================

def approve_issue(issue_number, mode, scope_report=None, actor="engineer"):
    state = load_state()
    num = str(issue_number)
    entry = state["issues"].get(num)

    if not entry:
        print(f"❌ Issue #{num} not in state. Run --scan first.")
        return

    if mode == "manual":
        entry["status"]     = "manual"
        entry["decision"]   = "manual"
        entry["updated_at"] = datetime.utcnow().isoformat() + "Z"
        log_audit(state, "marked_manual", num, "Engineer chose to handle manually", actor=actor)
        save_state(state)
        print(f"📋 Issue #{num} marked for manual handling.")
        return

    report     = scope_report or entry.get("scope_report") or "(Scoping report pending)"
    issue_data = {"number": int(num), "title": entry["title"], "body": entry["body"]}

    print(f"🤖 Dispatching Stage 2 fix session for issue #{num} (mode: {mode})...")
    result     = devin_post("sessions", {"prompt": build_fix_prompt(issue_data, report, mode)})
    session_id = result.get("session_id") or result.get("id")

    entry["status"]         = "fixing"
    entry["decision"]       = mode
    entry["fix_session_id"] = session_id
    entry["updated_at"]     = datetime.utcnow().isoformat() + "Z"
    log_audit(state, f"approved_{mode}", num, f"Fix session: {session_id}", actor=actor)
    save_state(state)

    post_github_comment(int(num),
        f"✅ **IssueFlow Stage 2 — Fix Approved** (`{mode}` mode)\n\n"
        f"Devin is implementing the fix based on the approved scoping report.\n\n"
        f"Devin session: https://app.devin.ai/sessions/{session_id}\n\n"
        f"A PR will be opened once all tests pass."
    )
    print(f"   ✅ Fix session: https://app.devin.ai/sessions/{session_id}")

# ============================================================
# ROLLBACK
# ============================================================

def rollback_issue(issue_number, actor="engineer"):
    state = load_state()
    num   = str(issue_number)
    entry = state["issues"].get(num)

    if not entry or not entry.get("pr_number"):
        print(f"❌ No PR found for issue #{num}.")
        return

    print(f"⏪ Rolling back issue #{num} — closing PR #{entry['pr_number']}...")
    close_pr_and_reopen_issue(entry["pr_number"], int(num))
    entry["status"]     = "rolled_back"
    entry["updated_at"] = datetime.utcnow().isoformat() + "Z"
    log_audit(state, "rolled_back", num, f"PR #{entry['pr_number']} closed", actor=actor)
    save_state(state)
    print(f"   ✅ Rollback complete.")

# ============================================================
# POLL DEVIN SESSIONS
# ============================================================

def poll_sessions():
    while True:
        try:
            state   = load_state()
            changed = False

            for num, entry in state["issues"].items():

                # Poll scope sessions
                if entry["status"] == "scoping" and entry.get("scope_session_id"):
                    sid = entry["scope_session_id"]
                    if sid.startswith("dry-run"):
                        continue
                    try:
                        session  = devin_get_session(sid)
                        if session.get("status") in ("finished", "completed", "stopped"):
                            messages = session.get("messages") or []
                            report   = next(
                                (m.get("content", "") for m in reversed(messages)
                                 if m.get("role") == "assistant"), "")
                            entry["scope_report"] = report
                            entry["status"]       = "awaiting_approval"
                            entry["updated_at"]   = datetime.utcnow().isoformat() + "Z"
                            log_audit(state, "scope_complete", num, "Scoping report ready")
                            changed = True
                    except Exception:
                        pass

                # Poll fix sessions
                if entry["status"] == "fixing" and entry.get("fix_session_id"):
                    sid = entry["fix_session_id"]
                    if sid.startswith("dry-run"):
                        continue
                    try:
                        session  = devin_get_session(sid)
                        if session.get("status") in ("finished", "completed", "stopped"):
                            pr_url    = session.get("pull_request_url") or ""
                            pr_number = None
                            if pr_url:
                                try:
                                    pr_number = int(pr_url.rstrip("/").split("/")[-1])
                                except Exception:
                                    pass
                            entry["status"]     = "pr_open" if pr_url else "fix_complete"
                            entry["pr_url"]     = pr_url
                            entry["pr_number"]  = pr_number
                            entry["updated_at"] = datetime.utcnow().isoformat() + "Z"
                            log_audit(state, "pr_opened", num, f"PR: {pr_url}")
                            changed = True
                    except Exception:
                        pass

            if changed:
                save_state(state)

        except Exception as e:
            print(f"[poll] {e}")

        time.sleep(30)

# ============================================================
# FLASK API SERVER
# ============================================================

def run_server():
    if not FLASK_AVAILABLE:
        print("❌ Run: pip install flask flask-cors")
        return

    app = Flask(__name__)
    CORS(app)

    @app.route("/api/issues")
    def api_issues():
        try:
            gh_issues = get_all_open_issues()
        except Exception as e:
            return jsonify({"error": str(e)}), 500
        state  = load_state()
        result = []
        for issue in gh_issues:
            num   = str(issue["number"])
            entry = state["issues"].get(num, {})
            result.append({
                "number":           issue["number"],
                "title":            issue["title"],
                "body":             issue["body"] or "",
                "html_url":         issue["html_url"],
                "created_at":       issue["created_at"],
                "file":             entry.get("file") or _guess_file(issue),
                "status":           entry.get("status", "new"),
                "classification":   entry.get("classification") or classify_issue(issue),
                "scope_report":     entry.get("scope_report"),
                "scope_session_id": entry.get("scope_session_id"),
                "fix_session_id":   entry.get("fix_session_id"),
                "pr_url":           entry.get("pr_url"),
                "pr_number":        entry.get("pr_number"),
                "decision":         entry.get("decision"),
                "updated_at":       entry.get("updated_at"),
            })
        return jsonify(result)

    @app.route("/api/audit")
    def api_audit():
        return jsonify(load_state().get("audit_log", []))

    @app.route("/api/scan", methods=["POST"])
    def api_scan():
        try:
            issues = get_all_open_issues()
            state  = load_state()
            for issue in issues:
                if str(issue["number"]) not in state["issues"]:
                    dispatch_scope_session(issue)
            return jsonify({"ok": True, "scanned": len(issues)})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/approve", methods=["POST"])
    def api_approve():
        data = flask_request.json
        try:
            approve_issue(
                data["issue_number"],
                data["mode"],
                scope_report=data.get("scope_report"),
                actor=data.get("actor", "engineer")
            )
            state = load_state()
            session_id = state["issues"].get(str(data["issue_number"]), {}).get("fix_session_id")
            return jsonify({"ok": True, "session_id": session_id})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/rollback", methods=["POST"])
    def api_rollback():
        data = flask_request.json
        try:
            rollback_issue(data["issue_number"], actor=data.get("actor", "engineer"))
            return jsonify({"ok": True})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/scope", methods=["POST"])
    def api_scope():
        data = flask_request.json
        try:
            issue = get_single_issue(data["issue_number"])
            dispatch_scope_session(issue)
            return jsonify({"ok": True})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    threading.Thread(target=poll_sessions, daemon=True).start()
    print("🚀 IssueFlow API running at http://localhost:5000")
    print("   Polling Devin sessions every 30s in background...")
    app.run(port=5000, debug=False)

# ============================================================
# CLI
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="IssueFlow — autonomous issue resolution via Devin")
    parser.add_argument("--scan",     action="store_true", help="Stage 1: scope all open issues")
    parser.add_argument("--issue",    type=int,            help="Stage 1: scope a single issue by number")
    parser.add_argument("--approve",  type=int,            help="Stage 2: approve an issue for fixing")
    parser.add_argument("--mode",     default="autofix",   help="autofix | review | manual")
    parser.add_argument("--rollback", type=int,            help="Close PR and reopen issue")
    parser.add_argument("--serve",    action="store_true", help="Run Flask API server for dashboard")
    parser.add_argument("--dry-run",  action="store_true", help="Preview without dispatching to Devin")
    args = parser.parse_args()

    check_config()

    if args.serve:
        run_server()
    elif args.scan:
        issues = get_all_open_issues()
        print(f"Found {len(issues)} open issue(s)")
        for issue in issues:
            dispatch_scope_session(issue, dry_run=args.dry_run)
    elif args.issue:
        dispatch_scope_session(get_single_issue(args.issue), dry_run=args.dry_run)
    elif args.approve is not None:
        approve_issue(args.approve, args.mode)
    elif args.rollback is not None:
        rollback_issue(args.rollback)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
