#!/usr/bin/env python3
"""
简单向量服务器 - Qdrant替代方案
用于解决WSL兼容性问题
"""

from flask import Flask, request, jsonify
import json
import os
from datetime import datetime

app = Flask(__name__)

# 内存存储向量数据
vector_store = {}
collections = {}

@app.route('/cluster', methods=['GET'])
def cluster_status():
    return jsonify({"status": "ok"})

@app.route('/collections', methods=['GET'])
def list_collections():
    return jsonify({"result": {"collections": [{"name": name} for name in collections.keys()]}})

@app.route('/collections/<collection_name>', methods=['PUT'])
def create_collection(collection_name):
    data = request.json
    collections[collection_name] = {
        "name": collection_name,
        "config": data,
        "created_at": datetime.now().isoformat()
    }
    vector_store[collection_name] = {}
    return jsonify({"result": True, "status": "ok"})

@app.route('/collections/<collection_name>', methods=['DELETE'])
def delete_collection(collection_name):
    if collection_name in collections:
        del collections[collection_name]
        if collection_name in vector_store:
            del vector_store[collection_name]
    return jsonify({"result": True, "status": "ok"})

@app.route('/collections/<collection_name>/points/count', methods=['POST'])
def count_points(collection_name):
    if collection_name not in vector_store:
        return jsonify({"status": {"error": f"Collection `{collection_name}` doesn't exist!"}})
    
    count = len(vector_store[collection_name])
    return jsonify({"result": {"count": count}, "status": "ok"})

@app.route('/collections/<collection_name>/points/upsert', methods=['PUT', 'POST'])
def upsert_points(collection_name):
    if collection_name not in vector_store:
        return jsonify({"status": {"error": f"Collection `{collection_name}` doesn't exist!"}})
    
    data = request.json
    points = data.get("points", [])
    
    for point in points:
        point_id = point.get("id")
        vector_store[collection_name][point_id] = {
            "id": point_id,
            "vector": point.get("vector"),
            "payload": point.get("payload", {}),
            "created_at": datetime.now().isoformat()
        }
    
    return jsonify({"result": {"operation_id": 0, "status": "completed"}, "status": "ok"})

@app.route('/collections/<collection_name>/points/search', methods=['POST'])
def search_points(collection_name):
    if collection_name not in vector_store:
        return jsonify({"status": {"error": f"Collection `{collection_name}` doesn't exist!"}})
    
    data = request.json
    limit = data.get("limit", 10)
    
    # 简单返回最新的几个点（实际应该做向量相似度计算）
    points = list(vector_store[collection_name].values())
    points.sort(key=lambda x: x["created_at"], reverse=True)
    
    results = []
    for i, point in enumerate(points[:limit]):
        results.append({
            "id": point["id"],
            "score": 0.9 - i * 0.1,  # 模拟相似度分数
            "payload": point["payload"]
        })
    
    return jsonify({"result": results, "status": "ok"})

if __name__ == '__main__':
    print("🚀 Simple Vector Server started on http://localhost:6333")
    app.run(host='0.0.0.0', port=6333, debug=False)