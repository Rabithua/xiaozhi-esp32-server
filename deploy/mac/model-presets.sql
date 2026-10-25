-- Optional, credential-free presets for an initialized manager database.
-- Run manually after manager-api has completed its schema migrations.
-- Existing credentials, defaults, agents and devices are never changed.
SET NAMES utf8mb4;
START TRANSACTION;

INSERT INTO ai_model_config
    (id, model_type, model_code, model_name, is_default, is_enabled,
     config_json, doc_link, remark, sort)
SELECT
    'ASR_MacQwenAudio31Stream', 'ASR', 'MacQwenAudio31Stream',
    'Qwen Audio 3.1 ASR Flash（流式）', 0, 1,
    '{"type":"aliyunbl_stream","api_key":"","ws_url":"wss://dashscope.aliyuncs.com/api-ws/v1/inference/","model":"qwen-audio-3.1-asr-flash-streaming","format":"pcm","sample_rate":16000,"output_dir":"tmp/"}',
    'https://help.aliyun.com/zh/model-studio/qwen-audio-3-1-asr-flash-streaming',
    '需填写百炼 API Key；业务空间密钥还需对应空间的 ws_url。需要本 fork 的 aliyunbl_stream 修复。', 30
WHERE NOT EXISTS (SELECT 1 FROM ai_model_config WHERE id = 'ASR_MacQwenAudio31Stream');

INSERT INTO ai_model_config
    (id, model_type, model_code, model_name, is_default, is_enabled,
     config_json, doc_link, remark, sort)
SELECT
    'LLM_MacQwenFlash', 'LLM', 'MacQwenFlash', 'Qwen Flash（百炼）', 0, 1,
    '{"type":"openai","api_key":"","base_url":"https://dashscope.aliyuncs.com/compatible-mode/v1","model_name":"qwen-flash","temperature":0.7,"max_tokens":500,"top_p":1,"frequency_penalty":0}',
    'https://help.aliyun.com/zh/model-studio/compatibility-of-openai-with-dashscope',
    '需填写百炼 API Key，并按业务空间和地域设置兼容接口地址。', 30
WHERE NOT EXISTS (SELECT 1 FROM ai_model_config WHERE id = 'LLM_MacQwenFlash');

INSERT INTO ai_model_config
    (id, model_type, model_code, model_name, is_default, is_enabled,
     config_json, doc_link, remark, sort)
SELECT
    'TTS_MacCosyVoiceV3Flash', 'TTS', 'MacCosyVoiceV3Flash',
    'CosyVoice V3 Flash（龙安台）', 0, 1,
    '{"type":"alibl_stream","api_key":"","ws_url":"wss://dashscope.aliyuncs.com/api-ws/v1/inference/","model":"cosyvoice-v3-flash","voice":"longantai_v3","format":"pcm","sample_rate":24000,"volume":50,"rate":1,"pitch":1,"output_dir":"tmp/"}',
    'https://help.aliyun.com/zh/model-studio/cosyvoice-voice-list',
    '需填写百炼 API Key；业务空间密钥还需对应空间的 ws_url。角色音色选择龙安台（台湾女声）。', 30
WHERE NOT EXISTS (SELECT 1 FROM ai_model_config WHERE id = 'TTS_MacCosyVoiceV3Flash');

INSERT INTO ai_tts_voice
    (id, tts_model_id, name, tts_voice, languages, sort)
SELECT
    'VOICE_MacLongantaiV3', 'TTS_MacCosyVoiceV3Flash',
    '龙安台（台湾女声）', 'longantai_v3', '普通话', 1
WHERE NOT EXISTS (SELECT 1 FROM ai_tts_voice WHERE id = 'VOICE_MacLongantaiV3');

-- Expose the optional endpoint on the existing ASR editor without replacing
-- its other fields. Re-importing does not append another ws_url field.
UPDATE ai_model_provider
SET fields = JSON_ARRAY_APPEND(
    COALESCE(fields, JSON_ARRAY()), '$',
    JSON_OBJECT('key', 'ws_url', 'label', 'WebSocket地址（含Workspace ID）',
                'type', 'string'))
WHERE id = 'SYSTEM_ASR_AliyunBLStream'
  AND JSON_CONTAINS(COALESCE(fields, JSON_ARRAY()),
                    JSON_OBJECT('key', 'ws_url')) = 0;

COMMIT;
