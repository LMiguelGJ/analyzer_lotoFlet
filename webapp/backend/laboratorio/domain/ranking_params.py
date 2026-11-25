"""Validation of the optional per-laboratory ``ranking_params`` (window, half-life, scope...).

Absent params mean today's fixed defaults (``causal_rankings.DEFAULT_PARAMS``); a lab only
stores what it overrides. Messages are Spanish because they reach the user as 422 details.
"""

from laboratorio.domain.number_lists import DEFAULT_LIST_ID, PARITY_SYSTEM

WINDOW_MIN, WINDOW_MAX = 10, 5000
HALF_LIFE_MIN, HALF_LIFE_MAX = 5, 5000
SCOPES = ("position", "any")
TIE_BREAKS = ("fixed", "seeded")
#: The seven rankings an ensemble can vote with (never the ensemble itself).
ENSEMBLE_COMPONENTS = (
    "cold",
    "freq_hist",
    "freq_recent",
    "decay",
    "transition",
    "overdue",
    "digits",
)

#: Keys each system accepts (``tie_break`` is accepted by all of them).
ALLOWED_KEYS = {
    "cold": ("scope",),
    "freq_hist": ("window", "scope"),
    "freq_recent": ("window",),
    "decay": ("half_life",),
    "transition": ("fallback_window",),
    "overdue": (),
    "digits": ("window",),
    "ensemble": ("components", "component_params"),
}

_WINDOW_MESSAGE = f"La ventana debe ser un número entero entre {WINDOW_MIN} y {WINDOW_MAX} sorteos."
_HALF_LIFE_MESSAGE = (
    f"La vida media debe ser un número entero entre {HALF_LIFE_MIN} y {HALF_LIFE_MAX} sorteos."
)
_SCOPE_MESSAGE = "«Mirar» debe ser «position» (1.er lugar) o «any» (cualquier lugar)."
_TIE_MESSAGE = "El desempate debe ser «fixed» (fijo) o «seeded» (variado)."


def _int_in(value, low, high):
    return type(value) is int and low <= value <= high


def _check_value(key, value):
    if key in ("window", "fallback_window"):
        if not _int_in(value, WINDOW_MIN, WINDOW_MAX):
            raise ValueError(_WINDOW_MESSAGE)
    elif key == "half_life":
        if not _int_in(value, HALF_LIFE_MIN, HALF_LIFE_MAX):
            raise ValueError(_HALF_LIFE_MESSAGE)
    elif key == "scope":
        if value not in SCOPES:
            raise ValueError(_SCOPE_MESSAGE)
    elif key == "tie_break" and value not in TIE_BREAKS:
        raise ValueError(_TIE_MESSAGE)


def _simple_params(system, params, *, where=""):
    allowed = (*ALLOWED_KEYS[system], "tie_break") if not where else ALLOWED_KEYS[system]
    for key, value in params.items():
        if key not in allowed:
            allowed_text = ", ".join(allowed) if allowed else "ninguno"
            raise ValueError(
                f"El parámetro «{key}» no existe para el sistema «{system}»{where}. "
                f"Permitidos: {allowed_text}."
            )
        if key == "window" and system == "freq_hist" and value is None:
            continue  # the whole history
        _check_value(key, value)
    return dict(params)


def _ensemble_params(params):
    result = {}
    components = params.get("components")
    if "components" in params:
        if type(components) not in (list, tuple):
            raise ValueError("Los componentes del ensamble deben ser una lista de sistemas.")
        components = list(components)
        if len(components) < 2:
            raise ValueError("El ensamble necesita al menos 2 componentes.")
        for component in components:
            if type(component) is not str or component not in ENSEMBLE_COMPONENTS:
                raise ValueError(
                    f"Componente desconocido del ensamble: «{component}». "
                    f"Posibles: {', '.join(ENSEMBLE_COMPONENTS)}."
                )
        if len(set(components)) != len(components):
            raise ValueError("Los componentes del ensamble no pueden repetirse.")
        result["components"] = components
    if "component_params" in params:
        per_component = params["component_params"]
        if not isinstance(per_component, dict):
            raise ValueError("Los parámetros de cada componente deben ser un objeto.")
        active = components if components is not None else list(ENSEMBLE_COMPONENTS)
        clean = {}
        for component, own in per_component.items():
            if component not in active:
                raise ValueError(
                    f"Hay parámetros para «{component}», que no es un componente del ensamble."
                )
            if not isinstance(own, dict):
                raise ValueError(f"Los parámetros de «{component}» deben ser un objeto.")
            if "tie_break" in own:
                raise ValueError("El desempate se elige para todo el ensamble, no por componente.")
            clean[component] = _simple_params(component, own, where=" (dentro del ensamble)")
        result["component_params"] = clean
    return result


def validate_ranking_params(system, list_id, value):
    """Canonical params (a new dict) or ``None``; ``ValueError`` with a Spanish message."""
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError("Los parámetros del sistema deben ser un objeto.")
    if not value:
        return None
    if list_id == DEFAULT_LIST_ID:
        raise ValueError(
            "Los parámetros del sistema no se pueden cambiar en Loteka Chance Express: "
            "usa sus rankings archivados."
        )
    if system == PARITY_SYSTEM:
        raise ValueError("Paridad no usa rankings: no admite parámetros del sistema.")
    if system not in ALLOWED_KEYS:
        raise ValueError(f"El sistema «{system}» no admite parámetros.")
    if system == "ensemble":
        extra = {k: v for k, v in value.items() if k not in ("components", "component_params")}
        result = _ensemble_params(value)
        result.update(_simple_params("overdue", extra))  # tie_break only
        return result
    return _simple_params(system, value)
