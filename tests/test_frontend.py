from dataclasses import replace

from conftest import FakeModel, FakeSources, run_api

from eventlens.api import create_app


def test_built_dashboard_is_served_without_exposing_runtime(settings, tmp_path):
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>EventLens</title>")
    (dist / "assets" / "app.js").write_text("console.log('test asset');")
    app = create_app(
        replace(settings, frontend_directory=dist), model=FakeModel(), sources=FakeSources()
    )

    async def exercise(client):
        assert (await client.get("/")).status_code == 200
        assert (
            (await client.get("/assets/app.js"))
            .headers["content-type"]
            .startswith("text/javascript")
        )
        assert (await client.get("/api/health")).json()["model_ready"]
        for path in (
            "/runtime/eventlens.sqlite3",
            "/.env",
            "/api/not-real",
            "/%2e%2e/test.sqlite3",
        ):
            response = await client.get(path)
            assert response.status_code == 404
            assert response.json()["error"]["code"] == "NOT_FOUND"

    run_api(app, exercise)


def test_unbuilt_frontend_does_not_break_api(settings, tmp_path):
    app = create_app(
        replace(settings, frontend_directory=tmp_path / "missing"),
        model=FakeModel(),
        sources=FakeSources(),
    )

    async def exercise(client):
        assert (await client.get("/")).status_code == 404
        assert (await client.get("/api/portfolio")).status_code == 200

    run_api(app, exercise)
