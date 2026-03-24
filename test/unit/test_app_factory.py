from server import create_app


def test_create_app_registers_core_routes():
    app = create_app()
    routes = {route.path for route in app.routes}

    assert "/" in routes
    assert "/api/download" in routes
    assert "/api/search" in routes
    assert "/api/parse" in routes
    assert "/api/auth/login" in routes
