#!/usr/bin/env python3
# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

# BM -> BMG compiler arithmetic tests

import unittest

import beanmachine.ppl as bm
import torch
from beanmachine.ppl.inference.bmg_inference import BMGInference
from torch.distributions import Bernoulli, Beta, Binomial, HalfCauchy, Normal


@bm.random_variable
def beta():
    return Beta(2.0, 2.0)


@bm.random_variable
def norm():
    return Normal(0.0, 1.0)


@bm.random_variable
def hc():
    return HalfCauchy(1.0)


@bm.functional
def expm1_prob():
    return beta().expm1()


@bm.functional
def expm1_real():
    return torch.expm1(norm())


@bm.functional
def expm1_negreal():
    return torch.Tensor.expm1(-hc())


@bm.functional
def logistic_prob():
    return beta().sigmoid()


@bm.functional
def logistic_real():
    return torch.sigmoid(norm())


@bm.functional
def logistic_negreal():
    return torch.Tensor.sigmoid(-hc())


@bm.random_variable
def ordinary_arithmetic(n):
    return Bernoulli(
        probs=torch.tensor(0.5) + torch.log(torch.exp(n * torch.tensor(0.1)))
    )


@bm.random_variable
def stochastic_arithmetic():
    s = 0.0
    # Verify that mutating += works on lists normally:
    items = [0]
    items += [1]
    # Verify that +=, *=, -= all work on graph nodes:
    for n in items:
        p = torch.log(torch.tensor(0.01))
        p *= ordinary_arithmetic(n)
        s += p
    m = 1
    m -= torch.exp(input=torch.log(torch.tensor(0.99)) + s)
    return Bernoulli(m)


@bm.functional
def mutating_assignments():
    # Torch supports mutating tensors in-place, which allows for
    # aliasing. THE COMPILER DOES NOT CORRECTLY DETECT ALIASING
    # WHEN A STOCHASTIC QUANTITY IS INVOLVED!
    x = torch.tensor(1.0)
    y = x  # y is an alias for x
    y += 2.0  # y is now 3, and so is x
    y = y + 4.0  # y is now 7, but x is still 3
    # So far we're all fine; every mutated tensor has been non-stochastic.
    b = beta() * x + y  # b is beta_sample * 3 + 7
    # Now let's see how things go wrong. We'll alias stochastic quantity b:
    c = b
    c *= 5.0
    # In Python Bean Machine, c and b are now both (beta() * 3 + 7) * 5
    # but the compiler does not detect that c and b are aliases, and does
    # not represent tensor mutations in graph nodes. The compiler thinks
    # that c is (beta() * 3 + 7) * 5 but b is still (beta() * 3 + 7):
    return b


@bm.random_variable
def neg_of_neg():
    return Normal(-torch.neg(norm()), 1.0)


@bm.functional
def subtractions():
    # Show that we can handle a bunch of different ways to subtract things
    # Show that unary plus operations are discarded.
    n = +norm()
    b = +beta()
    h = +hc()
    return +torch.sub(+n.sub(+b), +b - h)


@bm.random_variable
def bino():
    return Binomial(total_count=3, probs=0.5)


@bm.functional
def unsupported_invert():
    return ~bino()


@bm.functional
def unsupported_bitand():
    return bino() & bino()


@bm.functional
def unsupported_bitor():
    return bino() | bino()


@bm.functional
def unsupported_bitxor():
    return bino() ^ bino()


@bm.functional
def unsupported_floordiv():
    return bino() // bino()


@bm.functional
def unsupported_lshift():
    return bino() << bino()


@bm.functional
def unsupported_mod():
    return bino() % bino()


@bm.functional
def unsupported_rshift():
    return bino() >> bino()


@bm.functional
def unsupported_add():
    # What happens if we use a stochastic quantity in an operation with
    # a non-tensor, non-number?
    return bino() + "foo"


class BMGArithmeticTest(unittest.TestCase):
    def test_bmg_arithmetic_expm1(self) -> None:
        self.maxDiff = None

        observed = BMGInference().to_dot([expm1_prob()], {})
        expected = """
digraph "graph" {
  N0[label=2.0];
  N1[label=Beta];
  N2[label=Sample];
  N3[label=ToPosReal];
  N4[label=ExpM1];
  N5[label=Query];
  N0 -> N1;
  N0 -> N1;
  N1 -> N2;
  N2 -> N3;
  N3 -> N4;
  N4 -> N5;
}"""
        self.assertEqual(observed.strip(), expected.strip())

        observed = BMGInference().to_dot([expm1_real()], {})
        expected = """
digraph "graph" {
  N0[label=0.0];
  N1[label=1.0];
  N2[label=Normal];
  N3[label=Sample];
  N4[label=ExpM1];
  N5[label=Query];
  N0 -> N2;
  N1 -> N2;
  N2 -> N3;
  N3 -> N4;
  N4 -> N5;
}"""
        self.assertEqual(observed.strip(), expected.strip())

        observed = BMGInference().to_dot([expm1_negreal()], {})
        expected = """
digraph "graph" {
  N0[label=1.0];
  N1[label=HalfCauchy];
  N2[label=Sample];
  N3[label="-"];
  N4[label=ExpM1];
  N5[label=Query];
  N0 -> N1;
  N1 -> N2;
  N2 -> N3;
  N3 -> N4;
  N4 -> N5;
}"""
        self.assertEqual(observed.strip(), expected.strip())

    def test_bmg_arithmetic_logistic(self) -> None:
        self.maxDiff = None

        observed = BMGInference().to_dot([logistic_prob()], {})
        expected = """
digraph "graph" {
  N0[label=2.0];
  N1[label=Beta];
  N2[label=Sample];
  N3[label=ToReal];
  N4[label=Logistic];
  N5[label=Query];
  N0 -> N1;
  N0 -> N1;
  N1 -> N2;
  N2 -> N3;
  N3 -> N4;
  N4 -> N5;
}"""
        self.assertEqual(observed.strip(), expected.strip())

        observed = BMGInference().to_dot([logistic_real()], {})
        expected = """
digraph "graph" {
  N0[label=0.0];
  N1[label=1.0];
  N2[label=Normal];
  N3[label=Sample];
  N4[label=Logistic];
  N5[label=Query];
  N0 -> N2;
  N1 -> N2;
  N2 -> N3;
  N3 -> N4;
  N4 -> N5;
}"""
        self.assertEqual(observed.strip(), expected.strip())

        observed = BMGInference().to_dot([logistic_negreal()], {})
        expected = """
digraph "graph" {
  N0[label=1.0];
  N1[label=HalfCauchy];
  N2[label=Sample];
  N3[label="-"];
  N4[label=ToReal];
  N5[label=Logistic];
  N6[label=Query];
  N0 -> N1;
  N1 -> N2;
  N2 -> N3;
  N3 -> N4;
  N4 -> N5;
  N5 -> N6;
}"""
        self.assertEqual(observed.strip(), expected.strip())

    def test_bmg_misc_arithmetic(self) -> None:
        self.maxDiff = None
        observed = BMGInference().to_dot([stochastic_arithmetic()], {})
        expected = """
digraph "graph" {
  N00[label=0.5];
  N01[label=Bernoulli];
  N02[label=Sample];
  N03[label=0.6000000238418579];
  N04[label=Bernoulli];
  N05[label=Sample];
  N06[label=-0.010050326585769653];
  N07[label=-4.605170249938965];
  N08[label=0.0];
  N09[label=if];
  N10[label=if];
  N11[label="+"];
  N12[label=Exp];
  N13[label=complement];
  N14[label=Bernoulli];
  N15[label=Sample];
  N16[label=Query];
  N00 -> N01;
  N01 -> N02;
  N02 -> N09;
  N03 -> N04;
  N04 -> N05;
  N05 -> N10;
  N06 -> N11;
  N07 -> N09;
  N07 -> N10;
  N08 -> N09;
  N08 -> N10;
  N09 -> N11;
  N10 -> N11;
  N11 -> N12;
  N12 -> N13;
  N13 -> N14;
  N14 -> N15;
  N15 -> N16;
}
"""
        self.assertEqual(expected.strip(), observed.strip())

    def test_bmg_neg_of_neg(self) -> None:
        # This test shows that we treat torch.neg the same as the unary negation
        # operator when generating a graph.
        #
        # TODO: This test also shows that we do NOT optimize away negative-of-negative
        # which we certainly could. Once we implement that optimization, come back
        # and fix up this test accordingly.

        self.maxDiff = None
        observed = BMGInference().to_dot([neg_of_neg()], {})
        expected = """
digraph "graph" {
  N0[label=0.0];
  N1[label=1.0];
  N2[label=Normal];
  N3[label=Sample];
  N4[label="-"];
  N5[label="-"];
  N6[label=Normal];
  N7[label=Sample];
  N8[label=Query];
  N0 -> N2;
  N1 -> N2;
  N1 -> N6;
  N2 -> N3;
  N3 -> N4;
  N4 -> N5;
  N5 -> N6;
  N6 -> N7;
  N7 -> N8;
}
"""
        self.assertEqual(observed.strip(), expected.strip())

    def test_bmg_subtractions(self) -> None:
        # TODO: Notice in this code generation we end up with
        # the path:
        #
        # Beta -> Sample -> ToPosReal -> Negate -> ToReal -> MultiAdd
        #
        # We could optimize this path to
        #
        # Beta -> Sample -> ToReal -> Negate -> MultiAdd

        self.maxDiff = None
        observed = BMGInference().to_dot([subtractions()], {})
        expected = """
digraph "graph" {
  N00[label=0.0];
  N01[label=1.0];
  N02[label=Normal];
  N03[label=Sample];
  N04[label=2.0];
  N05[label=Beta];
  N06[label=Sample];
  N07[label=HalfCauchy];
  N08[label=Sample];
  N09[label=ToPosReal];
  N10[label="-"];
  N11[label=ToReal];
  N12[label=ToReal];
  N13[label="-"];
  N14[label=ToReal];
  N15[label="+"];
  N16[label="-"];
  N17[label="+"];
  N18[label=Query];
  N00 -> N02;
  N01 -> N02;
  N01 -> N07;
  N02 -> N03;
  N03 -> N17;
  N04 -> N05;
  N04 -> N05;
  N05 -> N06;
  N06 -> N09;
  N06 -> N12;
  N07 -> N08;
  N08 -> N13;
  N09 -> N10;
  N10 -> N11;
  N11 -> N17;
  N12 -> N15;
  N13 -> N14;
  N14 -> N15;
  N15 -> N16;
  N16 -> N17;
  N17 -> N18;
}
"""
        self.assertEqual(expected.strip(), observed.strip())

    def test_unsupported_arithmetic(self) -> None:
        self.maxDiff = None

        with self.assertRaises(ValueError) as ex:
            BMGInference().infer([unsupported_invert()], {}, 1)
        expected = """
The model uses a Invert operation unsupported by Bean Machine Graph.
The unsupported node is the operator of a Query.
        """
        observed = str(ex.exception)
        self.assertEqual(expected.strip(), observed.strip())

        with self.assertRaises(ValueError) as ex:
            BMGInference().infer([unsupported_bitand()], {}, 1)
        expected = """
The model uses a & operation unsupported by Bean Machine Graph.
The unsupported node is the operator of a Query.
        """
        observed = str(ex.exception)
        self.assertEqual(expected.strip(), observed.strip())

        with self.assertRaises(ValueError) as ex:
            BMGInference().infer([unsupported_bitor()], {}, 1)
        expected = """
The model uses a | operation unsupported by Bean Machine Graph.
The unsupported node is the operator of a Query.
        """
        observed = str(ex.exception)
        self.assertEqual(expected.strip(), observed.strip())

        with self.assertRaises(ValueError) as ex:
            BMGInference().infer([unsupported_bitxor()], {}, 1)
        expected = """
The model uses a ^ operation unsupported by Bean Machine Graph.
The unsupported node is the operator of a Query.
        """
        observed = str(ex.exception)
        self.assertEqual(expected.strip(), observed.strip())

        with self.assertRaises(ValueError) as ex:
            BMGInference().infer([unsupported_floordiv()], {}, 1)
        expected = """
The model uses a // operation unsupported by Bean Machine Graph.
The unsupported node is the operator of a Query.
        """
        observed = str(ex.exception)
        self.assertEqual(expected.strip(), observed.strip())

        with self.assertRaises(ValueError) as ex:
            BMGInference().infer([unsupported_lshift()], {}, 1)
        expected = """
The model uses a << operation unsupported by Bean Machine Graph.
The unsupported node is the operator of a Query.
        """
        observed = str(ex.exception)
        self.assertEqual(expected.strip(), observed.strip())

        with self.assertRaises(ValueError) as ex:
            BMGInference().infer([unsupported_mod()], {}, 1)
        expected = """
The model uses a % operation unsupported by Bean Machine Graph.
The unsupported node is the operator of a Query.
        """
        observed = str(ex.exception)
        self.assertEqual(expected.strip(), observed.strip())

        with self.assertRaises(ValueError) as ex:
            BMGInference().infer([unsupported_rshift()], {}, 1)
        expected = """
The model uses a >> operation unsupported by Bean Machine Graph.
The unsupported node is the operator of a Query.
        """
        observed = str(ex.exception)
        self.assertEqual(expected.strip(), observed.strip())

    def test_unsupported_operands(self) -> None:
        self.maxDiff = None
        with self.assertRaises(ValueError) as ex:
            BMGInference().infer([unsupported_add()], {}, 1)
        # TODO: This error message is terrible; fix it.
        expected = """
The model uses a foo operation unsupported by Bean Machine Graph.
The unsupported node is the right of a +.
        """
        observed = str(ex.exception)
        self.assertEqual(expected.strip(), observed.strip())

    def test_tensor_mutations_augmented_assignment(self) -> None:
        self.maxDiff = None

        # See notes in mutating_assignments() for details
        observed = BMGInference().to_dot([mutating_assignments()], {})
        expected = """
digraph "graph" {
  N0[label=2.0];
  N1[label=Beta];
  N2[label=Sample];
  N3[label=ToPosReal];
  N4[label=3.0];
  N5[label="*"];
  N6[label=7.0];
  N7[label="+"];
  N8[label=Query];
  N0 -> N1;
  N0 -> N1;
  N1 -> N2;
  N2 -> N3;
  N3 -> N5;
  N4 -> N5;
  N5 -> N7;
  N6 -> N7;
  N7 -> N8;
}
"""
        self.assertEqual(expected.strip(), observed.strip())
