"""Safe validation of a PyPI package spec entered through the UI.

The user never types a shell command — only a package name and (optionally) a version. This
module enforces a strict whitelist so the value can be passed as a single argv token to
``pip install`` (which we always invoke via an argument list, never a shell). URLs, VCS,
local paths and shell metacharacters are rejected.
"""
from __future__ import annotations

import re

# Characters that unambiguously indicate an injection / non-PyPI attempt. Note: ``>`` and ``<``
# are NOT here because they are legitimate version operators (e.g. requests>=2.32.0) and are
# harmless — pip is always invoked via an argv list, never through a shell.
DANGEROUS = [";", "&&", "||", "|", "$", "`", "..", "://", " ", "\t", "\n", "\\"]

# name(+extras)(version specifiers). Names per PEP 503; extras optional; specifiers optional.
_SPEC_RE = re.compile(
    r"^(?P<name>[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?)"
    r"(?P<extras>\[[A-Za-z0-9,._-]+\])?"
    r"(?P<spec>(?:(?:===|==|>=|<=|~=|!=|>|<)[A-Za-z0-9][A-Za-z0-9._*+!-]*)"
    r"(?:,(?:===|==|>=|<=|~=|!=|>|<)[A-Za-z0-9][A-Za-z0-9._*+!-]*)*)?$"
)


class ValidationResult:
    def __init__(self, *, valid: bool, package_name: str | None = None, version: str | None = None,
                 normalized_spec: str | None = None, error: str | None = None) -> None:
        self.valid = valid
        self.package_name = package_name
        self.version = version
        self.normalized_spec = normalized_spec
        self.error = error

    def as_dict(self) -> dict:
        return {
            "valid": self.valid,
            "package_name": self.package_name,
            "version": self.version,
            "normalized_spec": self.normalized_spec,
            "error": self.error,
        }


def build_spec(package: str | None, version: str | None, package_spec: str | None) -> str:
    """Combine the form inputs into a single spec string to validate."""
    if package_spec and package_spec.strip():
        return package_spec.strip()
    pkg = (package or "").strip()
    ver = (version or "").strip()
    if pkg and ver:
        # A bare version becomes an exact pin; an operator provided by the user is kept.
        if re.match(r"^(===|==|>=|<=|~=|!=|>|<)", ver):
            return f"{pkg}{ver}"
        return f"{pkg}=={ver}"
    return pkg


def validate_package_spec(raw: str) -> ValidationResult:
    spec = (raw or "").strip()
    if not spec:
        return ValidationResult(valid=False, error="Informe o nome da biblioteca.")
    if len(spec) > 300:
        return ValidationResult(valid=False, error="Especificação muito longa.")

    lowered = spec.lower()
    for bad in DANGEROUS:
        if bad in spec:
            return ValidationResult(valid=False, error=f"Caractere ou sequência não permitida: '{bad.strip() or bad}'.")
    for prefix in ("git+", "hg+", "svn+", "bzr+", "file:", "http:", "https:", "/", "./", "../", "~", "-"):
        if lowered.startswith(prefix):
            return ValidationResult(
                valid=False,
                error="Apenas pacotes do PyPI são permitidos (URLs, Git, caminhos locais e flags são bloqueados).",
            )

    m = _SPEC_RE.match(spec)
    if not m:
        return ValidationResult(valid=False, error="Formato inválido. Ex.: pandas, pandas==2.2.3, requests>=2.32.0.")

    name = m.group("name")
    extras = m.group("extras") or ""
    ver_spec = m.group("spec") or ""
    version = None
    exact = re.match(r"^==(?P<v>[^,]+)$", ver_spec)
    if exact:
        version = exact.group("v")
    normalized = f"{name}{extras}{ver_spec}"
    return ValidationResult(valid=True, package_name=name, version=version, normalized_spec=normalized)
