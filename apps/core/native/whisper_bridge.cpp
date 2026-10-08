// Narrow C ABI for the pinned whisper.cpp API. Private audio/text never goes to logs.
#include <atomic>
#include <algorithm>
#include <new>
#include "whisper.h"

struct mnemos_asr {
    whisper_context * context;
    std::atomic<bool> cancelled{false};
    std::atomic<bool> running{false};
};

static void quiet_log(enum ggml_log_level, const char *, void *) {}
static bool cancelled(void * data) {
    return static_cast<mnemos_asr *>(data)->cancelled.load();
}

extern "C" {
int mnemos_bridge_version() { return 1; }

void * mnemos_asr_create(const char * model, bool gpu) {
    whisper_log_set(quiet_log, nullptr);
    auto params = whisper_context_default_params();
    params.use_gpu = gpu;
    auto * context = whisper_init_from_file_with_params(model, params);
    if (!context) return nullptr;
    auto * state = new(std::nothrow) mnemos_asr;
    if (!state) { whisper_free(context); return nullptr; }
    state->context = context;
    return state;
}
void mnemos_asr_cancel(void * ptr) {
    static_cast<mnemos_asr *>(ptr)->cancelled.store(true);
}
int mnemos_asr_run(void * ptr, const float * samples, int count, const char * language) {
    auto * state = static_cast<mnemos_asr *>(ptr);
    if (state->cancelled.load()) return -1;
    auto params = whisper_full_default_params(WHISPER_SAMPLING_GREEDY);
    params.n_threads = 4;
    params.no_context = true;
    params.language = language;
    params.print_realtime = params.print_progress = params.print_timestamps = false;
    params.print_special = false;
    params.token_timestamps = true;
    params.abort_callback = cancelled;
    params.abort_callback_user_data = state;
    state->running.store(true);
    int result = whisper_full(state->context, params, samples, count);
    state->running.store(false);
    return result;
}
bool mnemos_asr_running(void * ptr) {
    return static_cast<mnemos_asr *>(ptr)->running.load();
}
const char * mnemos_asr_language(void * ptr) {
    return whisper_lang_str(whisper_full_lang_id(static_cast<mnemos_asr *>(ptr)->context));
}
int mnemos_asr_count(void * ptr) {
    return whisper_full_n_segments(static_cast<mnemos_asr *>(ptr)->context);
}
const char * mnemos_asr_text(void * ptr, int segment) {
    return whisper_full_get_segment_text(static_cast<mnemos_asr *>(ptr)->context, segment);
}
double mnemos_asr_start(void * ptr, int segment) {
    return whisper_full_get_segment_t0(static_cast<mnemos_asr *>(ptr)->context, segment) * .01;
}
double mnemos_asr_end(void * ptr, int segment) {
    return whisper_full_get_segment_t1(static_cast<mnemos_asr *>(ptr)->context, segment) * .01;
}
float mnemos_asr_confidence(void * ptr, int segment) {
    auto * ctx = static_cast<mnemos_asr *>(ptr)->context;
    float sum = 0; int count = 0;
    for (int token = 0; token < whisper_full_n_tokens(ctx, segment); ++token) {
        if (whisper_full_get_token_id(ctx, segment, token) >= whisper_token_eot(ctx)) continue;
        sum += whisper_full_get_token_p(ctx, segment, token); ++count;
    }
    return count ? std::clamp(sum / count, 0.f, 1.f) : 0;
}
void mnemos_asr_free(void * ptr) {
    if (!ptr) return;
    auto * state = static_cast<mnemos_asr *>(ptr);
    whisper_free(state->context); delete state;
}

void * mnemos_vad_create(const char * model) {
    whisper_log_set(quiet_log, nullptr);
    auto params = whisper_vad_default_context_params();
    params.n_threads = 1; params.use_gpu = false;
    return whisper_vad_init_from_file_with_params(model, params);
}
float mnemos_vad_probability(void * ptr, const float * samples, int count) {
    auto * ctx = static_cast<whisper_vad_context *>(ptr);
    if (count != 512 || !whisper_vad_detect_speech_no_reset(ctx, samples, count)) return -1;
    if (whisper_vad_n_probs(ctx) != 1) return -1;
    return whisper_vad_probs(ctx)[0];
}
void mnemos_vad_reset(void * ptr) { whisper_vad_reset_state(static_cast<whisper_vad_context *>(ptr)); }
void mnemos_vad_free(void * ptr) { if (ptr) whisper_vad_free(static_cast<whisper_vad_context *>(ptr)); }
}
