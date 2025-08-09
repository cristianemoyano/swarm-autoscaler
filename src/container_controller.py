from flask import request, jsonify
from main import App, SwarmService
from constants import SUPPORTED_METRICS

@App.route('/', methods=['GET'])
def root():
    return "Swarm Autoscaler is running", 200

@App.route('/api/container/stats', methods=['GET'])
def getContainerStats():
    """
        Api method get container stats by id if container running on this node.
        Supports metric selection: cpu (default) or memory.
    """
    containerId = request.args.get('id')
    metric = (request.args.get('metric') or 'cpu').lower()

    if not containerId:
        return jsonify({"error": "Missing required query parameter 'id'"}), 400

    if metric not in SUPPORTED_METRICS:
        return jsonify({"error": "Unsupported metric. Use 'cpu' or 'memory'"}), 400

    if metric == 'cpu':
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
        return {'ContainerId': containerId, 'cpu': value}
    else:
        value = SwarmService.getContainerMemoryStat(containerId)
        if value is None:
            return "Container with id=%s not running on this node" %(containerId), 404
        return {'ContainerId': containerId, 'memory': value}

