"""Generate portable JSON Schema from backend contracts."""

import json

from pydantic import BaseModel

from . import domain
from .runtime import ROOT


def main() -> None:
    contracts: list[type[BaseModel]] = [
        domain.Entity,
        domain.IdentityEntity,
        domain.Observation,
        domain.Event,
        domain.Evidence,
        domain.Utterance,
        domain.Conversation,
        domain.Memory,
        domain.Task,
        domain.Reminder,
        domain.ActionProposal,
        domain.ActionPolicyDecision,
        domain.ActionExecution,
    ]
    target = ROOT / "packages/contracts"
    target.mkdir(parents=True, exist_ok=True)
    for contract in contracts:
        (target / (contract.__name__ + ".schema.json")).write_text(
            json.dumps(contract.model_json_schema(), indent=2, ensure_ascii=False) + "\n"
        )


if __name__ == "__main__":
    main()
