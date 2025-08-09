from flask import request, jsonify
from main import App, SwarmService

@App.route('/', methods=['GET'])
def root():
    return "Swarm Autoscaler is running", 200

@App.route('/api/container/stats', methods=['GET'])
def getContainerStats():
    """
        Api method get container stats (cpu usage percent) by id if container running on this node
    """
    containerId = request.args.get('id')
    cpuLimitParam = request.args.get('cpuLimit')

    if not containerId:
        return jsonify({"error": "Missing required query parameter 'id'"}), 400
    if cpuLimitParam is None:
        return jsonify({"error": "Missing required query parameter 'cpuLimit'"}), 400
    try:
        cpuLimit = float(cpuLimitParam)
    except (TypeError, ValueError):
        return jsonify({"error": "Query parameter 'cpuLimit' must be a number"}), 400
    stats = SwarmService.getContainerCpuStat(containerId, cpuLimit)
    if(stats == None):
        return "Container with id=%s not running on this node" %(containerId), 404
    return {'ContainerId':containerId, 'cpu': stats}

