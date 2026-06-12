import numpy as np
import time

class SpatialMerger:
    """Merges detections from multiple cameras into a unified global ground plane with persistent IDs."""

    def __init__(self, proximity_threshold=100.0, track_ttl=2.0):
        # Threshold in ground-plane units
        self.proximity_threshold = proximity_threshold
        self.track_ttl = track_ttl
        self.cameras_homography = {} # camera_id -> matrix
        
        # Persistent Global Tracks: {global_id: {'x', 'y', 'last_seen'}}
        self.global_tracks = {}
        self.next_global_id = 1
        self._lock_time = 0

    def update_camera_homography(self, camera_id, matrix_list):
        if matrix_list:
            self.cameras_homography[camera_id] = np.array(matrix_list)
        else:
            self.cameras_homography.pop(camera_id, None)

    def project_point(self, camera_id, x, y):
        """Projects a camera pixel (x, y) to the global ground plane."""
        if camera_id not in self.cameras_homography:
            # print(f"DEBUG: Camera {camera_id} not in homography map: {list(self.cameras_homography.keys())}")
            return None
        
        matrix = self.cameras_homography[camera_id]
        point = np.array([x, y, 1.0])
        projected = np.dot(matrix, point)
        
        if projected[2] == 0:
            return None
            
        res = (projected[0] / projected[2], projected[1] / projected[2])
        # print(f"DEBUG: Cam {camera_id} ({x}, {y}) -> Global {res}")
        return res

    def cluster_and_match(self, all_detections):
        """
        Takes detections from all cameras, projects them, clusters them,
        and matches clusters to persistent Global IDs.
        
        Input: [{'camera_id': 1, 'local_id': 10, 'x': 100, 'y': 200}, ...]
        Output: (clusters, local_to_global_map)
        """
        now = time.time()
        global_points = []
        for det in all_detections:
            gp = self.project_point(det['camera_id'], det['x'], det['y'])
            if gp:
                global_points.append({
                    'gp': gp,
                    'camera_id': det['camera_id'],
                    'local_id': det.get('local_id', 0)
                })

        if not global_points:
            self._cleanup_tracks(now)
            return [], {}

        # 1. Clustering (Greedy Proximity)
        clusters = []
        for p in global_points:
            found_cluster = False
            for c in clusters:
                dist = np.sqrt((p['gp'][0] - c['x'])**2 + (p['gp'][1] - c['y'])**2)
                if dist < self.proximity_threshold:
                    c['points'].append(p)
                    # Simple average for centroid
                    pts = [pt['gp'] for pt in c['points']]
                    c['x'] = float(np.mean([pt[0] for pt in pts]))
                    c['y'] = float(np.mean([pt[1] for pt in pts]))
                    found_cluster = True
                    break
            
            if not found_cluster:
                clusters.append({
                    'x': float(p['gp'][0]),
                    'y': float(p['gp'][1]),
                    'points': [p]
                })

        # 2. Global ID Association (Match clusters to self.global_tracks)
        local_to_global = {}
        updated_tracks = {}

        for c in clusters:
            best_gid = None
            min_dist = self.proximity_threshold * 1.5
            
            for gid, track in self.global_tracks.items():
                dist = np.sqrt((c['x'] - track['x'])**2 + (c['y'] - track['y'])**2)
                if dist < min_dist:
                    min_dist = dist
                    best_gid = gid
            
            if best_gid is None:
                # New person entered the global space
                best_gid = self.next_global_id
                self.next_global_id += 1
            
            # Update track state
            c['global_id'] = best_gid
            updated_tracks[best_gid] = {'x': c['x'], 'y': c['y'], 'last_seen': now}
            
            # Map every local ID in this cluster to this Global ID
            for p in c['points']:
                local_to_global[(p['camera_id'], p['local_id'])] = best_gid

        # 3. Persistence: Keep tracks that were missed for a few frames
        for gid, track in self.global_tracks.items():
            if gid not in updated_tracks:
                if (now - track['last_seen']) < self.track_ttl:
                    updated_tracks[gid] = track

        self.global_tracks = updated_tracks
        
        # Result for BEV Map
        bev_results = []
        for c in clusters:
            bev_results.append({
                'id': c['global_id'],
                'x': c['x'],
                'y': c['y'],
                'cameras': list({p['camera_id'] for p in c['points']})
            })

        return bev_results, local_to_global

    def _cleanup_tracks(self, now):
        expired = [gid for gid, t in self.global_tracks.items() if (now - t['last_seen']) > self.track_ttl]
        for gid in expired:
            del self.global_tracks[gid]

    # Legacy method compatibility
    def get_unique_count(self, all_detections):
        clusters, _ = self.cluster_and_match(all_detections)
        return len(clusters)
