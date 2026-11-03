/* Web /apachas:
   - Formulario de gasto nuevo: según el tipo de reparto muestra casillas (a partes iguales) o un valor por
     miembro, y calcula en vivo lo que le toca a cada uno y si cuadra el total (el servidor lo vuelve a validar).
   - «Saldar»: abre el formulario de pago, rellenado con la deuda elegida; al cambiar a quién pagas, el importe
     pasa a ser lo que le debes (data-debo de cada opción; vacío si no le debes nada).
   - Borrar: pide un segundo clic (sin confirm(), que bloquea el navegador).
   - Importar de Splitwise: el nombre del miembro nuevo solo se ve si se elige «Crear miembro nuevo». */
(function () {
    "use strict";
    const num = (t) => {
        t = String(t || "").trim().replace(/\s|€/g, "");
        if (t.includes(",")) t = t.replace(/\./g, "").replace(",", ".");
        const n = parseFloat(t);
        return Number.isFinite(n) ? n : 0;
    };
    const fmt = (n) => n.toLocaleString("es-ES", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

    /** Céntimos de cada parte, igual que models/gasto.py:repartir (lo que sobra va a los primeros). */
    function repartir(totalC, pesos) {
        const suma = pesos.reduce((a, b) => a + b, 0);
        if (!suma) return pesos.map(() => 0);
        const partes = pesos.map((p) => Math.floor((totalC * p) / suma));
        let resto = totalC - partes.reduce((a, b) => a + b, 0);
        for (let i = 0; resto > 0; i = (i + 1) % partes.length, resto--) partes[i]++;
        return partes;
    }

    function initNuevo(form) {
        const filas = [...form.querySelectorAll(".gs-miembro")];
        const ayuda = form.querySelector(".gs-ayuda");
        const simbolo = form.dataset.importeLabel || "";
        function update() {
            const reparto = form.querySelector("[name=reparto]:checked").value;
            form.dataset.reparto = reparto;
            const total = num(form.importe.value);
            const totalC = Math.round(total * 100);
            const valores = filas.map((f) => num(f.querySelector(".gs-valor").value));
            const marcados = filas.map((f) => f.querySelector(".gs-check input").checked);
            let partes;
            let msg = "";
            let mal = false;
            if (reparto === "igual") {
                partes = repartir(totalC, marcados.map((m) => (m ? 1 : 0)));
                const n = marcados.filter(Boolean).length;
                msg = n ? `Entre ${n}: ${fmt(totalC / 100 / n)} ${simbolo} cada uno` : "Marca al menos a uno";
                mal = !n;
            } else if (reparto === "importes") {
                partes = valores.map((v) => Math.round(v * 100));
                const falta = totalC - partes.reduce((a, b) => a + b, 0);
                msg = falta ? `${falta > 0 ? "Faltan" : "Sobran"} ${fmt(Math.abs(falta) / 100)} ${simbolo}` : "Cuadra ✔";
                mal = !!falta;
            } else if (reparto === "porcentaje") {
                partes = repartir(totalC, valores);
                const suma = valores.reduce((a, b) => a + b, 0);
                msg = Math.abs(suma - 100) > 0.01 ? `Suman ${fmt(suma)} %, tienen que sumar 100 %` : "Suman 100 % ✔";
                mal = Math.abs(suma - 100) > 0.01;
            } else {
                partes = repartir(totalC, valores);
                const suma = valores.reduce((a, b) => a + b, 0);
                msg = suma ? `${fmt(suma)} partes en total` : "Pon cuántas partes paga cada uno";
                mal = !suma;
            }
            filas.forEach((f, i) => {
                f.querySelector(".gs-valor").placeholder = reparto === "porcentaje" ? "%" : reparto === "importes" ? simbolo : "partes";
                f.querySelector(".gs-parte").textContent = partes[i] ? `${fmt(partes[i] / 100)} ${simbolo}` : "—";
            });
            ayuda.textContent = msg;
            ayuda.classList.toggle("gs-neg", mal);
        }
        form.addEventListener("input", update);
        form.addEventListener("change", update);
        update();
    }

    function initSaldar() {
        const form = document.querySelector(".gs-saldar");
        if (!form) return;
        const rellenar = () => {
            const opcion = form.receptor_id.selectedOptions[0];
            form.importe.value = (opcion && opcion.dataset.debo) || "";
        };
        form.receptor_id.addEventListener("change", rellenar);
        document.querySelectorAll("[data-gs-saldar]").forEach((btn) =>
            btn.addEventListener("click", () => {
                if (btn.dataset.a) form.receptor_id.value = btn.dataset.a;
                else form.receptor_id.selectedIndex = 0;  // la primera opción es a quien más debo
                if (btn.dataset.importe) form.importe.value = btn.dataset.importe;
                else rellenar();
                form.hidden = false;
                form.scrollIntoView({ behavior: "smooth", block: "center" });
                form.importe.focus();
            }));
        form.querySelector("[data-gs-cerrar]").addEventListener("click", () => { form.hidden = true; });
    }

    function initConfirmar() {
        document.querySelectorAll("[data-gs-confirmar]").forEach((btn) =>
            btn.addEventListener("click", (ev) => {
                if (btn.classList.contains("gs-armado")) return;
                ev.preventDefault();
                btn.classList.add("gs-armado");
                btn.dataset.texto = btn.textContent;
                btn.textContent = "¿Seguro? Pulsa otra vez";
                setTimeout(() => {
                    btn.classList.remove("gs-armado");
                    btn.textContent = btn.dataset.texto;
                }, 4000);
            }));
    }

    function initPersonas() {
        document.querySelectorAll(".gs-persona").forEach((fila) => {
            const select = fila.querySelector("select");
            const nombre = fila.querySelector(".gs-persona-nombre");
            const update = () => { nombre.hidden = Boolean(select.value); };
            select.addEventListener("change", update);
            update();
        });
    }

    function init() {
        const nuevo = document.querySelector(".gs-nuevo");
        if (nuevo) initNuevo(nuevo);
        initSaldar();
        initConfirmar();
        initPersonas();
    }
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
    else init();
})();
