"""Being polite to the computer: memory, idle, battery, model fallback, release."""

from types import SimpleNamespace

from babel.pipeline.jobs import Worker, create_job, run_job
from babel.scenario.cascade import Cascade
from babel.system import Governor, Policy, load_prefs, save_prefs


def gov(avail=30.0, idle=999.0, battery=False, pressure=1, loaded=None, sizes=None, **policy):
    return Governor(Policy(**policy), probes={
        "available_gb": lambda: avail, "idle_seconds": lambda: idle, "on_battery": lambda: battery,
        "pressure_level": lambda: pressure, "ollama_loaded": lambda: dict(loaded or {}),
        "ollama_size_gb": lambda m: (sizes or {}).get(m)})


def test_memory_and_pressure():
    assert gov(avail=20).memory(12) is None
    assert "needs 14 GB" in gov(avail=10).memory(12)
    assert "pressure" in gov(avail=30, pressure=2).memory(1)
    assert gov(pressure=4).critical() and not gov(pressure=2).critical()


def test_background_work_waits_for_idle_and_mains_power():
    assert "using the computer" in gov(idle=10).background()
    assert gov(idle=600).background() is None
    assert gov(idle=10, background_when="always").background() is None
    assert "battery" in gov(idle=600, battery=True).background()
    assert gov(idle=600, battery=True, pause_on_battery=False).background() is None


def test_model_fallback_picks_what_fits():
    sizes = {"big": 18.0, "small": 5.0}
    assert gov(avail=40, sizes=sizes).pick_ollama_model(["big", "small"]) == "big"
    assert gov(avail=16, sizes=sizes).pick_ollama_model(["big", "small"]) == "small"
    assert gov(avail=16, sizes=sizes, loaded={"big": 18}).pick_ollama_model(["big", "small"]) == "big"  # already in
    assert gov(avail=3, sizes=sizes).pick_ollama_model(["big", "small"]) is None


def test_prefs_persist(store):
    p = Policy()
    save_prefs(store, p, background_when="always", pause_on_battery=False)
    again = load_prefs(store, Policy())
    assert again.background_when == "always" and again.pause_on_battery is False


def test_job_waits_at_the_gate_then_runs(store, tmp_path):
    nid = store.create_novel("t", [("c1", '"Hi," Tobin said.', "a"), ("c2", '"Bye," Mira said.', "b")])
    job = create_job(store, nid, tiers="rules")
    answers = iter(["waiting for memory: 9 GB free, needs 20 GB", None, None, None])
    seen = []

    def gate():
        reason = next(answers, None)
        seen.append(reason)
        return reason

    out = run_job(store, Cascade(), job, concurrency=1, gate=gate, gate_poll=0.01)
    assert out["status"] == "done" and out["done"] == 2 and seen[0].startswith("waiting for memory")


def test_worker_falls_back_to_a_smaller_model(store, monkeypatch):
    import babel.llm.providers as providers

    monkeypatch.setattr(providers, "ollama_models", lambda base=None: ["qwen3:30b-a3b", "qwen3:8b"])
    nid = store.create_novel("t", [("c1", "x", "a")])
    job = create_job(store, nid, tiers="local")
    local = SimpleNamespace(model="qwen3:30b-a3b", preferred="qwen3:30b-a3b", base_url="http://x")
    cascade = SimpleNamespace(local=local)
    g = gov(avail=12, sizes={"qwen3:30b-a3b": 18.0, "qwen3:8b": 5.2})
    w = Worker(store, lambda: cascade, governor=g)
    gate = w._choose_model(cascade, job)
    assert local.model == "qwen3:8b" and gate() is None
    assert "not enough free memory for qwen3:30b-a3b" in store.one("SELECT message FROM jobs WHERE id=?", (job,))["message"]
    # memory comes back: the next job uses the big model again
    g2 = gov(avail=40, sizes={"qwen3:30b-a3b": 18.0, "qwen3:8b": 5.2})
    Worker(store, lambda: cascade, governor=g2)._choose_model(cascade, job)
    assert local.model == "qwen3:30b-a3b"
