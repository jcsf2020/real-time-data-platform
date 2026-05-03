from fastapi.testclient import TestClient
from rtdp_api import app, format_prometheus_metrics


def test_format_prometheus_metrics_exports_latest_values() -> None:
    output = format_prometheus_metrics(
        [
            {"metric_name": "events_processed_total", "metric_value": 10.0},
            {"metric_name": "processing_lag_seconds", "metric_value": 2.5},
        ]
    )

    assert "# HELP rtdp_pipeline_metric_value Latest observed pipeline metric value." in output
    assert "# TYPE rtdp_pipeline_metric_value gauge" in output
    assert 'rtdp_pipeline_metric_value{metric_name="events_processed_total"} 10.0' in output
    assert 'rtdp_pipeline_metric_value{metric_name="processing_lag_seconds"} 2.5' in output


def test_metrics_prometheus_endpoint_returns_text_plain(monkeypatch) -> None:
    def fake_fetch_all(query: str, params: tuple = ()) -> list[dict]:
        assert "FROM observability.pipeline_metrics" in query
        assert params == ()
        return [
            {"metric_name": "latest_processed_offset", "metric_value": 42.0},
        ]

    monkeypatch.setattr("rtdp_api.fetch_all", fake_fetch_all)

    client = TestClient(app)
    response = client.get("/metrics-prometheus")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert 'rtdp_pipeline_metric_value{metric_name="latest_processed_offset"} 42.0' in response.text
