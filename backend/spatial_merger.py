import numpy as np
import json

class SpatialMerger:
    """Merges detections from multiple cameras into a unified global ground plane."""

    def __init__(self, proximity_threshold=100.0):
        # Threshold in ground-plane units (e.g., if 1000x1000 represents 10m x 10m, 100 units = 1m)
        self.proximity_threshold = proximity_threshold
        self.cameras_homography = {} # camera_id -> matrix

    def update_camera_homography(self, camera_id, matrix_list):
        if matrix_list:
            self.cameras_homography[camera_id] = np.array(matrix_list)
        else:
            if camera_id in self.cameras_homography:
                del self.cameras_homography[camera_id]

    def project_point(self, camera_id, x, y):
        """Projects a camera pixel (x, y) to the global ground plane."""
        if camera_id not in self.cameras_homography:
            return None
        
        matrix = self.cameras_homography[camera_id]
        point = np.array([x, y, 1.0])
        projected = np.dot(matrix, point)
        
        if projected[2] == 0:
            return None
            
        return (projected[0] / projected[2], projected[1] / projected[2])

    def deduplicate(self, all_detections):
        """
        Takes a list of detections: [{'camera_id': 1, 'x': 100, 'y': 200, 'id': 10}, ...]
        Returns a list of unique clusters: [{'id': 10, 'x': 500.5, 'y': 500.2, 'cameras': [1, 2]}]
        """
        global_points = []
        for det in all_detections:
            gp = self.project_point(det['camera_id'], det['x'], det['y'])
            if gp:
                global_points.append({
                    'gp': gp,
                    'camera_id': det['camera_id'],
                    'id': det.get('id', 0)
                })

        if not global_points:
            return []

        clusters = []
        # Simple greedy proximity clustering
        for p in global_points:
            found_cluster = False
            for c in clusters:
                dist = np.sqrt((p['gp'][0] - c['x'])**2 + (p['gp'][1] - c['y'])**2)
                if dist < self.proximity_threshold:
                    c['points'].append(p)
                    # Update average (centroid)
                    pts = [pt['gp'] for pt in c['points']]
                    c['x'] = float(np.mean([pt[0] for pt in pts]))
                    c['y'] = float(np.mean([pt[1] for pt in pts]))
                    c['cameras'].add(p['camera_id'])
                    found_cluster = True
                    break
            
            if not found_cluster:
                clusters.append({
                    'id': p['id'], # Use the tracker ID of the first point as the cluster ID
                    'x': float(p['gp'][0]),
                    'y': float(p['gp'][1]),
                    'points': [p],
                    'cameras': {p['camera_id']}
                })

        # Final cleanup for JSON serialization
        results = []
        for c in clusters:
            results.append({
                'id': c['id'],
                'x': c['x'],
                'y': c['y'],
                'cameras': list(c['cameras'])
            })

        return results

    def get_unique_count(self, all_detections):
        """Returns the total unique person count across all cameras."""
        clusters = self.deduplicate(all_detections)
        return len(clusters)
