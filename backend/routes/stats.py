"""Stats and AI analytics routes."""
from flask import Blueprint, jsonify, request

stats_bp = Blueprint('stats', __name__)

# These will be set by app.py during initialization
_ai_engine = None
_get_stats = None
_reset_stats = None
_memory = None


def init_stats_routes(ai_engine, get_stats_fn, reset_stats_fn, memory=None):
    global _ai_engine, _get_stats, _reset_stats, _memory
    _ai_engine = ai_engine
    _get_stats = get_stats_fn
    _reset_stats = reset_stats_fn
    _memory = memory


@stats_bp.route("/api/stats")
def stats_api():
    return jsonify(_get_stats())


@stats_bp.route("/api/stats/reset", methods=["POST"])
def stats_reset_api():
    print("🧹 [API] Reset stats requested")
    if _reset_stats:
        _reset_stats()
        print("✅ [API] Reset stats call completed")
    else:
        print("⚠️ [API] _reset_stats function NOT FOUND")
    return jsonify({"status": "reset"})



@stats_bp.route("/api/ai_insights")
def ai_insights_api():
    return jsonify(_ai_engine.get_insights())


@stats_bp.route("/api/ai_events")
def ai_events_api():
    return jsonify(_ai_engine.get_events())


@stats_bp.route("/api/ai_heatmap")
def ai_heatmap_api():
    return jsonify(_ai_engine.get_heatmap_data())



@stats_bp.route("/api/ai_query", methods=["POST"])
def ai_query_api():
    data = request.get_json()
    query = data.get("query", "") if data else ""
    if not query:
        return jsonify({"error": "No query provided"}), 400
    response = _ai_engine.handle_query(query)
    return jsonify({"query": query, "response": response})



@stats_bp.route("/api/chat_history")
def chat_history_api():
    """Return AI chat conversation history from persistent memory."""
    if not _memory:
        return jsonify([])
    limit = request.args.get("limit", 50, type=int)
    return jsonify(_memory.get_chat_history(limit=limit))

