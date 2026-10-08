# Extension — automatic person approval and names

User request: approve people automatically and associate names from audio or the panel.
2026-10-09 delivery: automatically accepted temporary display names from fresh final IT/EN
introductions when one face is continuously visible, plus direct owner name assignment/correction
from the panel without a second approval. ADR-034 defines ambiguity, freshness, loss and scope.
Verified with unit/API tests, actual model replay, routing benchmark and isolated UI/Stop.

Remaining: persistent automatic enrollment/verified cross-session identification. Existing
person consent and biometric enrollment flows remain separate. The earlier scope question about
registered people vs new non-biometric contacts has not received an answer; elapsed time does
not supply consent or permission to retain unknown identities. This temporary annotation path
is not completion of persistent matching requirements or the whole requested extension.
