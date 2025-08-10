from flask import request, jsonify, render_template
from main import App, SwarmService
from constants import SUPPORTED_METRIC_STRINGS, parse_metric, metric_to_str
from events import Events


@App.route('/', methods=['GET'])
def root():
    return "Swarm Autoscaler is running", 200


@App.route('/api/events', methods=['GET'])
def list_events():
    service = request.args.get('service')
    try:
        limit = int(request.args.get('limit')) if request.args.get('limit') else 100
    except ValueError:
        limit = 100
    return {"events": Events.list_events(limit=limit, service=service)}

@App.route('/api/events/clear', methods=['POST'])
def clear_events():
    service = request.args.get('service')
    deleted = Events.clear(service=service)
    return {"cleared": deleted, "service": service or None}


@App.route('/events/ui', methods=['GET'])
def events_ui():
    return render_template('events.html'), 200, {"Content-Type": "text/html; charset=utf-8"}


@App.route('/api/container/stats', methods=['GET'])
def getContainerStats():
    """
        Api method get container stats by id if container running on this node.
        Supports metric selection: cpu (default) or memory.
    """
    containerId = request.args.get('id')
    metric = (request.args.get('metric') or '').lower()
    metric_enum = parse_metric(metric)

    if not containerId:
        return jsonify({"error": "Missing required query parameter 'id'"}), 400

    if metric and metric not in SUPPORTED_METRIC_STRINGS:
        return jsonify({"error": "Unsupported metric. Use 'cpu' or 'memory'"}), 400

    if metric_enum.name == 'CPU':
        cpuLimitParam = request.args.get('cpuLimit')
        if cpuLimitParam is None:
            return jsonify({"error": "Missing required query parameter 'cpuLimit' for metric=cpu"}), 400
        try:
            cpuLimit = float(cpuLimitParam)
        except (TypeError, ValueError):
            return jsonify({"error": "Query parameter 'cpuLimit' must be a number"}), 400
        value = SwarmService.getContainerCpuStat(containerId, cpuLimit)
        if value is None:
            return "Container with id=%s not running on this node" %(containerId), 404
        return {'ContainerId': containerId, metric_to_str(metric_enum): value}
    else:
        value = SwarmService.getContainerMemoryStat(containerId)
        if value is None:
            return "Container with id=%s not running on this node" %(containerId), 404
        return {'ContainerId': containerId, metric_to_str(metric_enum): value}


