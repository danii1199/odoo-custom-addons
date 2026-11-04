"""El hueco de Cardio es cardio de verdad; los Cardio-Fuerza (Mixto) cuentan como fuerza (2026-11-04)."""
from odoo.tests import TransactionCase, tagged

from ..services import catalog, generator


def _rutina(i, title, tt, minutes, summary=""):
    return {"fuerta_id": i, "data": {"id": i, "title": title, "trainingType": tt, "durationMinutes": minutes,
                                     "intensity": "high", "summary": summary, "materials": ["No Material"],
                                     "url": catalog.POST_URL + str(i), "description": ""}}


@tagged("post_install", "-at_install")
class TestCardio(TransactionCase):

    def test_mixto_no_es_cardio(self):
        it = catalog.enrich({"title": "Entrenamiento híbrido 10", "trainingType": "Mixto",
                             "summary": "Combinación de fuerza y cardio", "description": ""})
        self.assertEqual(it["group"], "Fullbody")
        self.assertEqual(catalog.enrich({"title": "Cardio-Fuerza 3", "trainingType": "Mixto"})["group"], "Fullbody")
        self.assertEqual(catalog.enrich({"title": "HIIT 4", "trainingType": "Cardiovascular"})["group"], "Cardio")

    def test_torso_y_cardio(self):
        self.env["fuerta.history"].search([]).unlink()
        self.env["fuerta.routine"].search([]).unlink()
        filas = [_rutina(1, "Calentamiento 1", "Calentamiento", 10)]
        filas += [_rutina(10 + i, f"Fuerza torso {i}", "Fuerza", 20) for i in range(4)]
        filas += [_rutina(20 + i, f"Hombros {i}", "Fuerza", 5) for i in range(4)]
        filas += [_rutina(30 + i, f"Cardio-Fuerza {i}", "Mixto", 10, "Combinación de fuerza y cardio") for i in range(6)]
        filas += [_rutina(40 + i, f"HIIT {i}", "Cardiovascular", 15) for i in range(3)]
        self.env["fuerta.routine"].create(filas)
        for seed in range(30):
            res = generator.generate(self.env, {"minutes": 45, "groups": ["Torso", "Cardio"], "warmup": True,
                                                "seed": seed})
            tipos = [(b["group"], b["trainingType"]) for b in res["blocks"]]
            self.assertIn(("Cardio", "Cardiovascular"), tipos, tipos)
            self.assertNotIn(("Cardio", "Mixto"), tipos)
            self.assertEqual(res["total"], 45)

    def test_cardio_fuerza_rellena_la_fuerza(self):
        self.env["fuerta.history"].search([]).unlink()
        self.env["fuerta.routine"].search([]).unlink()
        filas = [_rutina(10 + i, f"Fuerza pierna {i}", "Fuerza", 20) for i in range(2)]
        filas += [_rutina(30 + i, f"Cardio-Fuerza {i}", "Mixto", 10) for i in range(6)]
        self.env["fuerta.routine"].create(filas)
        res = generator.generate(self.env, {"minutes": 60, "groups": ["Pierna y glúteo"], "seed": 1})
        self.assertIn("Fullbody", {b["group"] for b in res["blocks"]})
        self.assertEqual(res["total"], 60)
