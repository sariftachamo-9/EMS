import math

def calculate_distance(lat1, lon1, lat2, lon2):
    """
    Calculate the great circle distance between two points 
    on the earth (specified in decimal degrees) using Haversine formula.
    Returns distance in meters.
    """
    if lat1 is None or lon1 is None or lat2 is None or lon2 is None:
        return float('inf')
        
    # Convert decimal degrees to radians 
    lat1, lon1, lat2, lon2 = map(math.radians, [float(lat1), float(lon1), float(lat2), float(lon2)])

    # Haversine formula 
    dlon = lon2 - lon1 
    dlat = lat2 - lat1 
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a)) 
    r = 6371000 # Radius of earth in meters.
    return c * r

def verify_location_access(lat, lng, accuracy=None):
    """
    Consolidated location verification logic.
    - Accuracy Guard: Reject if accuracy > 200m
    - Haversine Check: Check against primary office and satellite offices.
    Returns (is_allowed, message, distance)
    """
    from database.models import OfficeSettings, AllowedLocation
    
    # 1. Accuracy Guard
    if accuracy is not None and float(accuracy) > 200:
        return False, f"GPS Accuracy ({int(accuracy)}m) exceeds 200m limit.", 0
        
    if lat is None or lng is None:
        return False, "Location coordinates missing.", 0

    settings = OfficeSettings.query.first()
    if not settings:
        return True, "Office settings not configured. Geofencing bypassed.", 0
        
    # 2. Check Primary Office
    dist = calculate_distance(lat, lng, settings.latitude, settings.longitude)
    if dist <= settings.radius:
        return True, "Main Office", dist
        
    # 3. Check Satellite Offices (AllowedLocation)
    allowed_locs = AllowedLocation.query.filter_by(is_active=True).all()
    for loc in allowed_locs:
        d = calculate_distance(lat, lng, loc.latitude, loc.longitude)
        if d <= loc.radius:
            return True, loc.name, d
            
    return False, f"Outside office radius (Distance: {int(dist)}m).", dist
