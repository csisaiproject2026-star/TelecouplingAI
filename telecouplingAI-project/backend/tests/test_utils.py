"""
Tests for shared/utils.py
"""
import json
import os
import pytest
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shared.utils import (
    CSISError,
    parse_input_data,
    validate_required,
    generate_output_dir,
    build_result_urls,
)


# --- parse_input_data ---

def test_parse_input_data_dict():
    assert parse_input_data({"a": 1}) == {"a": 1}


def test_parse_input_data_json_string():
    assert parse_input_data('{"a": 1}') == {"a": 1}


def test_parse_input_data_python_dict_string():
    result = parse_input_data("{'a': 1}")
    assert result == {"a": 1}


def test_parse_input_data_invalid_string():
    with pytest.raises(CSISError) as exc_info:
        parse_input_data("not valid json")
    assert exc_info.value.error_code == "INVALID_PARAMS"


def test_parse_input_data_invalid_type():
    with pytest.raises(CSISError) as exc_info:
        parse_input_data(12345)
    assert exc_info.value.error_code == "INVALID_PARAMS"


# --- validate_required ---

def test_validate_required_all_present():
    validate_required({"a": 1, "b": 2}, ["a", "b"])


def test_validate_required_missing():
    with pytest.raises(CSISError) as exc_info:
        validate_required({}, ["nodes_table"])
    assert exc_info.value.error_code == "MISSING_PARAMS"
    assert "nodes_table" in exc_info.value.message


def test_validate_required_empty_value():
    with pytest.raises(CSISError) as exc_info:
        validate_required({"a": ""}, ["a"])
    assert exc_info.value.error_code == "MISSING_PARAMS"


# --- generate_output_dir ---

def test_generate_output_dir_creates_dir(tmp_path, monkeypatch):
    from config import settings as _settings
    monkeypatch.setattr(_settings, "SHARED_DIR", str(tmp_path))
    abs_path, folder_name = generate_output_dir("test_tool", "session123")
    assert os.path.isdir(abs_path)
    assert "session123" in folder_name
    assert "test_tool" in folder_name


# --- build_result_urls ---

def test_build_result_urls(monkeypatch):
    from config import settings as _settings
    monkeypatch.setattr(_settings, "FILE_SERVER_URL", "http://localhost:8001/download/")
    files = [
        {"filename": "out.tif",   "render_type": "download", "path": "/tmp/out.tif"},
        {"filename": "stats.csv", "render_type": "csv",      "path": "/tmp/stats.csv"},
        {"filename": "out_preview.png", "render_type": "image", "path": "/tmp/out_preview.png"},
    ]
    results = build_result_urls("sess/20240101_tool", files)
    assert len(results) == 3
    assert results[0]["url"] == "http://localhost:8001/download/sess/20240101_tool/out.tif"
    assert results[0]["render_type"] == "download"
    assert results[1]["render_type"] == "csv"
    assert results[2]["render_type"] == "image"


def test_build_result_urls_with_subfolder(monkeypatch):
    from config import settings as _settings
    monkeypatch.setattr(_settings, "FILE_SERVER_URL", "http://localhost:8001/download/")
    files = [{"filename": "out.csv", "render_type": "csv", "path": "/tmp/out.csv"}]
    results = build_result_urls("sess/dir", files, subfolder="sub")
    assert "sub/out.csv" in results[0]["url"]
