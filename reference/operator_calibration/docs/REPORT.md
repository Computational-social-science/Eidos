# Operator calibration study

**Question.** Can a small language model's own output be used as a gate — that is, can its
abstention signal and its confidence tell a reader when to trust an answer?

**Instrument.** `StartLux-Decision-v1.1-4B-AutoThink-GGUF`, served locally, asked as a
three-way choice (`yes` / `no` / `not_stated`) over 100 items: 50 answerable from the state
and 50 not answerable from it. Truth is constructed by the item generator, so the study is
about the instrument, not about the world.

**Cost.** 100 forward passes, about 25 s wall clock, no training, no corpus.

## Result

On this item set the abstention signal separates the two classes completely: 50 of 50 unanswerable items were abstained on and 0 of 50 answerable items were abstained on (Fisher exact p = 2.0e-29). Every answerable item was answered correctly, which is a result about the items as much as about the model.

Confidence, by contrast, cannot be validated here: no threshold can be identified because the operator made no errors on answerable items. Precision is 1.000 at every floor on the tuning half; the held-out half acts on 23 of 50 items at precision 1.000 (95% Wilson interval 0.86–1.00). The lowest confidence on a correct answer is 0.54, so a floor at or below that loses nothing measurable and a higher floor has nothing to separate.

**The honest reading.** Abstention is informative; confidence is not measurable at this
difficulty. A threshold that looks perfect because the task is too easy is the failure mode
this study exists to display, and the right response is harder items, not a looser claim.

## What is not claimed

Other models, other prompt shapes, and other item difficulties. The study measures one
instrument on one constructed set; nothing here transfers without repeating the measurement.
