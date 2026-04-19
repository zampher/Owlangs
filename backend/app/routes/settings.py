# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Settings API routes for Owlangs.

This module contains routes for application settings management,
including anonymization settings and model configuration.
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from backend.app.models.anonymize import (
    _AnonSavePayload,
    _AnonTestPayload,
    _PerLangSavePayload,
    _AnonDownloadPayload,
)
from backend.config.config_loader import get_unified_config, save_unified_config
from logger import unified_logger as logger
from logger.logger import LogModule
from backend.app.services.version_service import check_update as check_update_service
# Delay import of PresidioModelManager to ensure module_logging is enabled first
# from anonymize.model_manager import PresidioModelManager

router = APIRouter()


@router.get("/api/log-messages")
async def get_log_messages():
    """Get log messages for frontend internationalization"""
    try:
        from logger.log_messages import get_frontend_log_messages
        return get_frontend_log_messages()
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.post("/api/log-language")
async def set_log_language_endpoint():
    """Log language is always English (simplified)"""
    # Logs are always in English, no need to change
    return {"status": "success", "language": "en", "message": "Logs are always in English"}


@router.get("/i18n/i18nMain.json")
async def get_i18n_main():
    """Get main i18n data"""
    try:
        import json
        from pathlib import Path
        from utils.resource_utils import resource_path
        
        i18n_file = Path(resource_path("i18n")) / "i18nMain.json"
        if i18n_file.exists():
            with open(i18n_file, 'r', encoding='utf-8-sig') as f:
                return json.load(f)
        else:
            # Return fallback data
            return {
                "zh": {
                    "init_i18n_failed_alert": "Failed to load interface translation resources, please check network connection or contact administrator.",
                    "init_failed_alert": "Initialization failed, could not connect to the backend service. Please check if the service is running or refresh the page."
                },
                "en": {
                    "init_i18n_failed_alert": "Failed to load interface translations. Please check your network connection or contact an administrator.",
                    "init_failed_alert": "Initialization failed, could not connect to the backend service. Please ensure the service is running and refresh the page."
                }
            }
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.get("/i18n/i18nLogin.json")
async def get_i18n_login():
    """Get login i18n data"""
    try:
        import json
        from pathlib import Path
        from utils.resource_utils import resource_path
        
        i18n_file = Path(resource_path("i18n")) / "i18nLogin.json"
        if i18n_file.exists():
            with open(i18n_file, 'r', encoding='utf-8-sig') as f:
                return json.load(f)
        else:
            # Return fallback data
            return {
                "login_title": "Login",
                "username": "Username", 
                "password": "Password",
                "login_button": "Login",
                "login_failed": "Login failed",
            }
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.get("/api/settings/anonymize")
async def get_anonymize_settings():
    """Get anonymization settings."""
    try:
        cfg = get_unified_config()
        model_name = getattr(getattr(cfg, 'anonymize', {}), 'model_name', 'zh_core_web_sm')
        models_dir = getattr(getattr(cfg, 'paths', {}), 'spacy_models_dir', None)
        return {"ok": True, "model_name": model_name, "models_dir": models_dir}
    except Exception as e:
        return JSONResponse(status_code=200, content={"ok": False, "message": str(e)})


@router.post("/api/settings/anonymize")
async def save_anonymize_settings(payload: _AnonSavePayload):
    """Save anonymization settings."""
    try:
        cfg = get_unified_config()
        if not hasattr(cfg, 'anonymize'):
            setattr(cfg, 'anonymize', type('x', (), {})())
        cfg.anonymize.model_name = payload.model_name
        if payload.models_dir:
            if not hasattr(cfg, 'paths'):
                setattr(cfg, 'paths', type('x', (), {})())
            cfg.paths.spacy_models_dir = payload.models_dir
            # Update runtime model search path immediately
            try:
                from pathlib import Path
                from anonymize.model_manager import PresidioModelManager
                PresidioModelManager.PROJECT_MODELS_DIR = Path(payload.models_dir)
            except Exception:
                pass
        # persist to disk
        try:
            save_unified_config()
        except Exception:
            pass
        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/settings/anonymize/test")
async def test_anonymize_model(payload: _AnonTestPayload):
    """Test anonymization model."""
    try:
        test_text = payload.text or "今天天气不错，张三的邮箱是 zhangsan@example.com"
        requested = payload.model_name

        # Apply models_dir override (affects PresidioModelManager search path)
        try:
            if payload.models_dir:
                from pathlib import Path
                from anonymize.model_manager import PresidioModelManager
                PresidioModelManager.PROJECT_MODELS_DIR = Path(payload.models_dir)
        except Exception:
            pass

        # Use the same Presidio initialization path as workflow
        from anonymize.language_detector import LanguageDetector, PresidioLanguageEngine
        lang = 'zh'
        ldet = LanguageDetector()
        plang = PresidioLanguageEngine(ldet)
        ok, analyzer, anonymizer = plang.initialize_engine_for_language(lang, model_name=requested)
        if not ok or analyzer is None:
            remediation = [
                "Ensure spaCy model is installed in models_dir",
                "Install spacy-curated-transformers for *trf models",
                "Verify numpy/torch versions in current venv",
                "Run: uv run python -m spacy validate"
            ]
            return JSONResponse(status_code=200, content={"ok": False, "message": f"Model '{requested}' not compatible or not loadable via Presidio.", "remediation": remediation})

        # Run Presidio analyze with a standard entity set
        try:
            entities = [
                "PERSON","ORGANIZATION","LOCATION","EMAIL_ADDRESS","PHONE_NUMBER","CREDIT_CARD","IP_ADDRESS","URL","DATE_TIME"
            ]
            results = analyzer.analyze(text=test_text, language=lang, entities=entities)
            used_model = requested  # Presidio hides internal model name; echo requested
            resp = {"ok": True, "message": f"Loaded {used_model}. Entities: {len(results)}", "requested_model": requested, "used_model": used_model}
            return resp
        except Exception as e:
            return JSONResponse(status_code=200, content={"ok": False, "message": str(e), "remediation": ["Check Presidio compatibility and spaCy pipeline components"]})
    except Exception as e:
        return JSONResponse(status_code=200, content={"ok": False, "message": str(e), "remediation": ["Check server logs for traceback", "Validate spaCy and model installation"]})


@router.get("/api/settings/anonymize/models")
async def get_per_language_models():
    """Get per-language model configuration."""
    try:
        cfg = get_unified_config()
        models = getattr(getattr(cfg, 'anonymize', {}), 'models', None)
        if hasattr(models, 'items'):
            data = { k: {"preferred": getattr(v, 'preferred', None), "models_dir": getattr(v, 'models_dir', None), "fallback": bool(getattr(v, 'fallback', True)) } for k, v in models.items() }
        else:
            data = {}
        options = {
            # 中文 - 4种模型
            "zh": ["zh_core_web_trf","zh_core_web_lg","zh_core_web_md","zh_core_web_sm"],
            # 英文 - 4种模型
            "en": ["en_core_web_trf","en_core_web_lg","en_core_web_md","en_core_web_sm"],
            # 德语 - 4种模型
            "de": ["de_core_news_trf","de_core_news_lg","de_core_news_md","de_core_news_sm"],
            # 法语 - 4种模型
            "fr": ["fr_core_news_trf","fr_core_news_lg","fr_core_news_md","fr_core_news_sm"],
            # 西班牙语 - 4种模型
            "es": ["es_core_news_trf","es_core_news_lg","es_core_news_md","es_core_news_sm"],
            # 意大利语 - 4种模型
            "it": ["it_core_news_trf","it_core_news_lg","it_core_news_md","it_core_news_sm"],
            # 荷兰语 - 4种模型
            "nl": ["nl_core_news_trf","nl_core_news_lg","nl_core_news_md","nl_core_news_sm"],
            # 葡萄牙语 - 4种模型
            "pt": ["pt_core_news_trf","pt_core_news_lg","pt_core_news_md","pt_core_news_sm"],
            # 俄语 - 4种模型
            "ru": ["ru_core_news_trf","ru_core_news_lg","ru_core_news_md","ru_core_news_sm"],
            # 日语 - 4种模型
            "ja": ["ja_core_news_trf","ja_core_news_lg","ja_core_news_md","ja_core_news_sm"],
            # 韩语 - 4种模型
            "ko": ["ko_core_news_trf","ko_core_news_lg","ko_core_news_md","ko_core_news_sm"],
            # 波兰语 - 4种模型
            "pl": ["pl_core_news_trf","pl_core_news_lg","pl_core_news_md","pl_core_news_sm"],
            # 丹麦语 - 4种模型
            "da": ["da_core_news_trf","da_core_news_lg","da_core_news_md","da_core_news_sm"],
            # 挪威语 - 4种模型
            "nb": ["nb_core_news_trf","nb_core_news_lg","nb_core_news_md","nb_core_news_sm"],
            # 瑞典语 - 4种模型
            "sv": ["sv_core_news_trf","sv_core_news_lg","sv_core_news_md","sv_core_news_sm"],
            # 芬兰语 - 4种模型
            "fi": ["fi_core_news_trf","fi_core_news_lg","fi_core_news_md","fi_core_news_sm"],
            # 希腊语 - 仅小型模型
            "el": ["el_core_news_sm"],
            # 立陶宛语 - 仅小型模型
            "lt": ["lt_core_news_sm"],
            # 罗马尼亚语 - 仅小型模型
            "ro": ["ro_core_news_sm"],
            # 乌克兰语 - 仅小型模型
            "uk": ["uk_core_news_sm"],
            # 阿拉伯语 - 仅小型模型
            "ar": ["ar_core_news_sm"],
            # 印地语 - 仅小型模型
            "hi": ["hi_core_news_sm"],
            # 泰语 - 仅小型模型
            "th": ["th_core_news_sm"],
            # 越南语 - 仅小型模型
            "vi": ["vi_core_news_sm"],
        }
        
        # Check model status for each model
        from anonymize.model_manager import PresidioModelManager
        
        model_status = {}
        for lang, model_list in options.items():
            model_status[lang] = {}
            for model_name in model_list:
                # Check if model is installed (use fast check - only checks file existence, doesn't load model)
                logger.info(
                    LogModule.ROUTE,
                    f"[MODEL_CHECK] Checking model: {model_name} for language: {lang}"
                )
                logger.info(
                    LogModule.ROUTE,
                    f"[MODEL_CHECK] PROJECT_MODELS_DIR: {PresidioModelManager.PROJECT_MODELS_DIR}"
                )
                logger.info(
                    LogModule.ROUTE,
                    f"[MODEL_CHECK] PROJECT_MODELS_DIR exists: {PresidioModelManager.PROJECT_MODELS_DIR.exists()}"
                )
                
                project_exists, system_exists = PresidioModelManager._check_model_exists_fast(model_name)
                logger.info(
                    LogModule.ROUTE,
                    f"[MODEL_CHECK] Model {model_name}: project_exists={project_exists}, system_exists={system_exists}"
                )
                
                is_installed = project_exists or system_exists
                logger.info(
                    LogModule.ROUTE,
                    f"[MODEL_CHECK] Model {model_name}: is_installed={is_installed}"
                )
                
                model_status[lang][model_name] = {
                    "installed": is_installed,
                    "status": "installed" if is_installed else "not_installed"
                }
        
        return {"ok": True, "models": data, "options": options, "model_status": model_status}
    except Exception as e:
        return JSONResponse(status_code=200, content={"ok": False, "message": str(e)})


@router.post("/api/settings/anonymize/models")
async def save_per_language_model(payload: _PerLangSavePayload):
    """Save per-language model configuration."""
    try:
        cfg = get_unified_config()
        if not hasattr(cfg, 'anonymize'):
            setattr(cfg, 'anonymize', type('x', (), {})())
        if not hasattr(cfg.anonymize, 'models') or not isinstance(cfg.anonymize.models, dict):
            cfg.anonymize.models = {}
        cfg.anonymize.models[payload.language] = type('x', (), {})()
        cfg.anonymize.models[payload.language].preferred = payload.preferred
        cfg.anonymize.models[payload.language].models_dir = payload.models_dir
        cfg.anonymize.models[payload.language].fallback = payload.fallback
        # runtime update of project dir when provided
        if payload.models_dir:
            try:
                from pathlib import Path
                from anonymize.model_manager import PresidioModelManager
                PresidioModelManager.PROJECT_MODELS_DIR = Path(payload.models_dir).parent if Path(payload.models_dir).name.startswith(payload.language+"_core_") else Path(payload.models_dir)
            except Exception:
                pass
        try:
            save_unified_config()
        except Exception:
            pass
        return {"ok": True}
    except Exception as e:
        return JSONResponse(status_code=200, content={"ok": False, "message": str(e)})


@router.post("/api/settings/anonymize/download")
async def download_anonymize_model(payload: _AnonDownloadPayload):
    """Download anonymization model."""
    try:
        lang = payload.language
        model = payload.model_name
        # Lazy import to avoid circulars and ensure availability
        from anonymize.model_manager import PresidioModelManager
        from pathlib import Path
        
        # resolve models_dir - always use deployment directory for Windows
        # Models should be downloaded to C:\ProgramData\Owlangs\models\spacy
        import os
        from anonymize.model_manager import PresidioModelManager
        if os.name == 'nt':  # Windows
            # Use deployment directory (C:\ProgramData\Owlangs\models\spacy)
            target_dir = PresidioModelManager.DEPLOYMENT_MODELS_DIR
            # Ensure directory exists
            target_dir.mkdir(parents=True, exist_ok=True)
            # Update PROJECT_MODELS_DIR to use deployment directory
            PresidioModelManager.PROJECT_MODELS_DIR = target_dir
        else:
            # For non-Windows, use provided models_dir or config
            target_dir = None
            if payload.models_dir:
                target_dir = Path(payload.models_dir)
                # Update PROJECT_MODELS_DIR if provided
                PresidioModelManager.PROJECT_MODELS_DIR = target_dir.parent if target_dir.name.startswith(lang+"_core_") else target_dir
            else:
                cfg = get_unified_config()
                spacy_models_dir = getattr(getattr(cfg, 'paths', {}), 'spacy_models_dir', None)
                if spacy_models_dir:
                    target_dir = Path(spacy_models_dir)
        
        # Check if model already exists before attempting download
        model_exists = PresidioModelManager.check_model_availability(lang, model)
        
        if model_exists:
            message = f"Model {model} is already installed"
            status = "exists"
            success = True
        else:
            # Use PresidioModelManager.download_models to download
            # Note: download_models returns bool, not (bool, str) tuple
            # Also note: AUTO_DOWNLOAD_DISABLED might prevent download
            if PresidioModelManager.AUTO_DOWNLOAD_DISABLED:
                message = f"Auto-download is disabled. Please install model {model} manually using: python -m spacy download {model}"
                status = "disabled"
                success = False
            else:
                success = PresidioModelManager.download_models(language=lang, model_name=model, force=False)
                
                if success:
                    message = f"Model {model} downloaded successfully"
                    status = "downloaded"
                else:
                    message = f"Failed to download model {model}. Please try installing manually: python -m spacy download {model}"
                    status = "failed"
        
        return {
            "ok": success,
            "message": message,
            "status": status,
            "dir": str(target_dir) if target_dir else str(PresidioModelManager.PROJECT_MODELS_DIR)
        }
    except Exception as e:
        return JSONResponse(status_code=200, content={"ok": False, "message": str(e)})


@router.get("/i18n/i18nSettings.json")
async def get_i18n_settings():
    """Get settings i18n data"""
    try:
        import json
        from pathlib import Path
        from utils.resource_utils import resource_path
        
        i18n_file = Path(resource_path("i18n")) / "i18nSettings.json"
        if i18n_file.exists():
            with open(i18n_file, 'r', encoding='utf-8-sig') as f:
                return json.load(f)
        else:
            # Return fallback data
            return {
                "en": {
                    "settingsTitle": "Settings",
                    "generalSettings": "General Settings",
                    "saveButton": "Save",
                    "cancelButton": "Cancel"
                }
            }
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.get("/api/settings/version")
async def get_version():
    """Get application version from backend."""
    try:
        from backend import __version__, __version_type__
        return {
            "ok": True,
            "version": __version__,
            "version_type": __version_type__,
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})


@router.get("/api/settings/update-check")
async def update_check():
    """Check for newer application version using GitHub Releases."""
    try:
        result = await check_update_service()
        return result
    except Exception as e:
        logger.error(
            LogModule.SYSTEM,
            f"[UPDATE-CHECK] Failed to perform update check: {e}",
            exc_info=True,
        )
        return JSONResponse(
            status_code=500,
            content={"ok": False, "error": "update_check_failed"},
        )

@router.get("/api/settings/system")
async def get_system_settings():
    """Get system config (e.g. features.show_ads) for frontend."""
    try:
        cfg = get_unified_config()
        return {
            "ok": True,
            "features": {
                "show_ads": getattr(cfg.system.features, "show_ads", False),
            },
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})


@router.patch("/api/settings/system")
async def patch_system_settings(payload: dict):
    """Update system config (e.g. features.show_ads). Persists to system.json."""
    try:
        from backend.config.system_config import clear_system_config_cache
        cfg = get_unified_config()
        if "features" in payload and isinstance(payload["features"], dict):
            f = payload["features"]
            if "show_ads" in f:
                cfg.system.features.show_ads = bool(f["show_ads"])
        save_unified_config()
        clear_system_config_cache()
        return {
            "ok": True,
            "features": {"show_ads": cfg.system.features.show_ads},
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})


@router.get("/api/settings/paths")
async def get_config_paths():
    """Get configuration file paths, including static.json path for translation statistics."""
    try:
        from utils.path_utils import get_config_file_path, get_configs_dir, get_owlangs_paths
        
        static_json_path = get_config_file_path("static.json")
        configs_dir = get_configs_dir()
        all_paths = get_owlangs_paths()
        
        return {
            "ok": True,
            "static_json_path": str(static_json_path),
            "configs_dir": str(configs_dir),
            "paths": all_paths
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})


@router.get("/api/settings/static-json")
async def get_static_json():
    """Get translation statistics from static.json file. No app version in response (use GET /api/settings/version if needed)."""
    try:
        import json
        from utils.path_utils import get_config_file_path

        static_json_path = get_config_file_path("static.json")

        if not static_json_path.exists():
            return {
                "ok": True,
                "translation_stats": {
                    "document_count": 0,
                    "page_count": 0,
                    "last_updated": None
                },
                "recorded_translation_flows": []
            }

        with open(static_json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return {"ok": True, **data}
    except Exception as e:
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})


@router.put("/api/settings/static-json")
async def update_static_json(payload: dict):
    """Update translation statistics in static.json file. App version is not stored in file."""
    try:
        import json
        from utils.path_utils import get_config_file_path

        static_json_path = get_config_file_path("static.json")

        # Do not store app version in file; inject on read from backend.__version__
        payload = {k: v for k, v in payload.items() if k != "version"}

        static_json_path.parent.mkdir(parents=True, exist_ok=True)
        with open(static_json_path, 'w', encoding='utf-8') as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

        return {"ok": True, "message": "Statistics updated successfully"}
    except Exception as e:
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})
