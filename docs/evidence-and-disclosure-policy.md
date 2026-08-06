# Evidence and disclosure policy

Raw transport artifacts are private and must be written outside this repository.
They are hashed before any CAP extraction occurs. Sanitized public artifacts are
separate files under `evidence/<release-id>/` and receive independent digests.

Publication requires a sanitized artifact, a cleared source license, an explicit
`sanitized_public` disclosure level, a public digest, extractor version, and the
frozen suite fingerprint. If any condition is absent, publish only no artifact.
