# Maintained Hermes core patches

These patches preserve local fixes that may be overwritten by `hermes update`.

## Multiplex cron profile routing

`hermes-core-multiplex-cron-profile-routing.patch` fixes cron delivery in a
multiplexed gateway by passing each profile's authenticated adapter map to its
own cron jobs. It was validated with Lens delivery to `#alpha-reports`.

After a Hermes update, from the Hermes checkout:

```bash
git apply /home/neurosovereign/projects/hermes-matrix-tng/patches/hermes-core-multiplex-cron-profile-routing.patch
```

If the patch no longer applies cleanly, inspect the affected scheduler and
gateway code before adapting it; do not force-apply it over changed logic.
