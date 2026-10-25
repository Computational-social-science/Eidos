# Referee simulation

## O1. A simulation with a planted truth proves nothing about the world.
[RESOLVED] Agreed, and the report says so in its first limitation. What it proves is that the
pipeline can separate a valid estimator from a corrupted one — the property a validation gate
needs before it is pointed at data whose truth is unknown.

## O2. Four hundred simulations is a lot of compute for a demo.
[RESOLVED] It is one second of numpy: 400 x 200 draws. The cost of the demo is not compute but
the discipline it demonstrates, and the acceptance gate refuses the corrupted estimator on the
same run.
