def csrf_exempt(route_handler):
    route_handler._csrf_exempt = True
    return route_handler
