from backend.app.db.models import AiProfile
from backend.app.db.store import store
from backend.app.services.ai_curator import DEFAULT_CURATOR_PROMPT

DEFAULT_PROFILE_NAME = "Padrao - Utilidades para casa"


def ensure_default_profile() -> AiProfile:
    state = store.load()
    if state.ai_profiles:
        return state.ai_profiles[0]

    profile = AiProfile(name=DEFAULT_PROFILE_NAME, prompt=DEFAULT_CURATOR_PROMPT.strip())
    return store.upsert_ai_profile(profile)


def list_profiles() -> list[AiProfile]:
    ensure_default_profile()
    return sorted(store.load().ai_profiles, key=lambda profile: profile.created_at)


def get_profile_prompt(profile_id: str | None) -> str:
    profiles = list_profiles()
    if profile_id:
        selected = next((profile for profile in profiles if profile.id == profile_id), None)
        if selected:
            return selected.prompt
    return profiles[0].prompt
