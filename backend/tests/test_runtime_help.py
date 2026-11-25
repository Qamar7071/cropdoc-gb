"""When the AI engine (ONNX Runtime) cannot start, the app must say so clearly, not ask to retrain."""

from __future__ import annotations

import builtins

from app.services.inference import InferenceService, runtime_help

WINDOWS_ERROR = (
    "DLL load failed while importing onnxruntime_pybind11_state: The specified module could not be found."
)


def test_windows_dll_error_points_to_the_vc_redistributable():
    message = runtime_help(ImportError(WINDOWS_ERROR), platform="win32")
    assert "Visual C++ Redistributable" in message and "vc_redist.x64.exe" in message
    assert "start.bat" in message and "train_quick" not in message


def test_other_import_errors_get_a_generic_engine_message():
    message = runtime_help(ImportError("No module named 'onnxruntime'"), platform="linux")
    assert "could not be imported" in message and "Visual C++" not in message


def test_service_reports_engine_problem_instead_of_model_problem(monkeypatch, tiny_model_dir):
    real_import = builtins.__import__

    def failing_import(name, *args, **kwargs):
        if name == "onnxruntime":
            raise ImportError(WINDOWS_ERROR)
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", failing_import)
    monkeypatch.setattr("sys.platform", "win32")
    service = InferenceService.load(tiny_model_dir)
    assert service.loaded is False
    assert "Visual C++ Redistributable" in service.reason
