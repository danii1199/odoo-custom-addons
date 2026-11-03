/* «Plan sigilo»: rutina propia de 30 min (no es de FuertaFit) para los días sin tiempo. Sombra de boxeo y fuerza
   sin saltos ni ruido, con un temporizador mudo: solo avisa con la pantalla y, si quieres, vibrando (móvil). */
const Sigilo = (() => {
  // Cada paso: n (nombre), s (segundos), tip (cómo hacerlo en silencio), alt (versión con mancuernas, opcional),
  // rest (segundos de cambio después). Bloques con laps se repiten esas vueltas. Total: 30:00 justos.
  const PLAN = [
    { name: "Calentamiento", steps: [
      { n: "Marcha sin impacto + círculos de brazos", s: 60, tip: "Rodillas a la altura de la cadera y apoya el pie de puntillas, sin ruido. Brazos en círculos amplios." },
      { n: "Sombra suave", s: 60, tip: "Guardia arriba, jab y directo al 50 %. Los pies se deslizan, nunca golpean el suelo." },
      { n: "Sentadilla con alcance", s: 60, tip: "Baja en 2 s y sube estirando los brazos hacia el techo." },
      { n: "Gusano (inchworm)", s: 60, tip: "Manos al suelo, camina con ellas hasta la plancha y vuelve. Despacio, sin flexión todavía." },
    ] },
    { name: "Sombra en sigilo · 3 asaltos", steps: [
      { n: "Asalto 1 · Rectos y pies", s: 150, rest: 30, tip: "Jab, jab-directo, 1-2-3. Muévete en todas direcciones arrastrando el pie de puntillas. Codos pegados, golpe y vuelta rápida a la guardia.",
        alt: "Con mancuernas muy ligeras (máx. 1 kg) si quieres. Nunca bloquees el codo al estirar." },
      { n: "Asalto 2 · Combinaciones y esquivas", s: 150, rest: 30, tip: "1-2-gancho, 1-2-3-2, uppercuts. Tras cada serie, esquiva rotando el tronco y baja a media sentadilla (flexionando rodillas, no la cintura)." },
      { n: "Asalto 3 · Ráfagas", s: 150, rest: 30, tip: "20 s de rectos a máxima velocidad / 10 s de guardia y esquivas, hasta el final. Velocidad, no ruido: los pies no se despegan." },
    ] },
    { name: "Fuerza muda · 2 vueltas", laps: 2, steps: [
      { n: "Sentadilla lenta con pausa", s: 40, rest: 20, tip: "3 s bajando, 1 s parado abajo, sube fuerte. Sin rebotes.",
        alt: "Sentadilla goblet: una mancuerna sujeta contra el pecho." },
      { n: "Flexiones a cámara lenta", s: 40, rest: 20, tip: "3 s bajando hasta que el pecho roce el suelo. Con rodillas apoyadas si hace falta para no perder la técnica.",
        alt: "Press de suelo con mancuernas: tumbado, baja hasta que los codos rocen el suelo sin golpearlo." },
      { n: "Zancada estática", s: 40, rest: 20, tip: "Pies fijos, uno delante y otro detrás: solo sube y baja, sin dar pasos. 20 s cada pierna, 3 s bajando hasta casi tocar el suelo con la rodilla.",
        alt: "Con una mancuerna en cada mano, brazos estirados." },
      { n: "Remo inclinado", s: 40, rest: 20, tip: "Con una mochila cargada (libros, botellas): espalda recta inclinada, lleva el codo hacia la cadera y aprieta 1 s.",
        alt: "Remo a una mano con mancuerna: 20 s cada brazo, apoyando la otra mano en una silla." },
      { n: "Puente de glúteo a una pierna", s: 40, rest: 20, tip: "20 s cada pierna. Aprieta el glúteo 1 s arriba y baja en 2 s.",
        alt: "Hip thrust a dos piernas con la mancuerna sobre la cadera." },
      { n: "Plancha rodilla al codo", s: 40, rest: 20, tip: "En plancha alta, lleva despacio la rodilla al codo del mismo lado y vuelve, alternando. El pie se posa, no cae. Aprieta el abdomen todo el rato." },
    ] },
    { name: "Final a tope", steps: [
      { n: "Sombra a máxima velocidad", s: 40, rest: 20, tip: "Todo lo que te quede: rectos rapidísimos con la guardia arriba. Pies quietos y en silencio." },
      { n: "Silla en la pared", s: 40, rest: 20, tip: "Espalda en la pared y muslos paralelos al suelo. Aguanta sin moverte.",
        alt: "Con una mancuerna sobre cada muslo." },
      { n: "Plancha con golpes", s: 40, rest: 20, tip: "En plancha alta, un puñetazo al frente alternando brazos, sin girar la cadera." },
    ] },
    { name: "Bajar pulsaciones", steps: [
      { n: "Andar suave y respirar", s: 60, tip: "Anda despacio: inhala 4 s por la nariz y exhala 6 s." },
      { n: "Estirar cadera y pecho", s: 60, tip: "30 s de zancada baja (15 s por lado) y 30 s de pecho abierto con el brazo en el marco de una puerta." },
    ] },
  ];
  const RULES = [
    "Cero saltos y cero impactos: los pies nunca se despegan del suelo de golpe ni caen. Pensada para pisos con vecinos.",
    "Si un pie se mueve, se posa despacio, como si hubiera alguien durmiendo debajo.",
    "Descalzo o con calcetines sobre una esterilla o alfombra.",
    "Las mancuernas no se sueltan nunca: déjalas en una toalla.",
    "La intensidad sale de la bajada lenta, las pausas y el poco descanso, no del impacto.",
    "Respira por la nariz y suelta el aire sin resoplar.",
  ];

  // Lista plana de pasos para el temporizador: los descansos entre ejercicios son pasos propios (con `pause`).
  const STEPS = [];
  PLAN.forEach((b, bi) => {
    for (let lap = 1; lap <= (b.laps || 1); lap++)
      b.steps.forEach((st, si) => {
        STEPS.push({ ...st, block: b.name + (b.laps ? ` (${lap}/${b.laps})` : ""), bi, si });
        if (st.rest) STEPS.push({ n: "Descanso", s: st.rest, pause: true, block: b.name, bi, si });
      });
  });
  const TOTAL = STEPS.reduce((s, x) => s + x.s, 0);

  const opts = Object.assign({ weights: false, vibrate: true }, store("ff-sigilo") || {});
  let idx = 0, left = STEPS[0].s, endAt = 0, timer = null, lock = null, finished = false;

  const mmss = s => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
  const tipOf = st => opts.weights && st.alt ? st.alt : st.tip;
  const buzz = p => { if (opts.vibrate && navigator.vibrate) navigator.vibrate(p); };

  function nextWork(i) { for (let j = i + 1; j < STEPS.length; j++) if (!STEPS[j].pause) return STEPS[j]; return null; }

  function setup() {
    $("sgRules").innerHTML = RULES.map(r => `<li>${esc(r)}</li>`).join("");
    $("sgTotal").textContent = mmss(TOTAL);
    for (const [id, key] of [["sgWeights", "weights"], ["sgVibrate", "vibrate"]]) {
      const el = $(id);
      el.classList.toggle("on", opts[key]);
      el.onclick = () => { opts[key] = !opts[key]; el.classList.toggle("on", opts[key]); store("ff-sigilo", opts); renderList(); render(); };
    }
    $("sgPlay").onclick = () => timer ? pause() : start();
    $("sgPrev").onclick = () => go(Math.max(0, idx - 1));
    $("sgNext").onclick = () => go(Math.min(STEPS.length - 1, idx + 1));
    $("sgReset").onclick = () => { pause(); finished = false; go(0); };
    renderList();
    render();
  }

  // Lista de la rutina (sin los descansos, que se ven en el temporizador). Clic en un ejercicio = saltar a él.
  function renderList() {
    $("sgList").innerHTML = PLAN.map((b, bi) => {
      const mins = Math.round(STEPS.filter(x => x.bi === bi).reduce((s, x) => s + x.s, 0) / 60);
      return `<div class="sg-block"><h3>${esc(b.name)} <small>${mins} min</small></h3>
        ${b.steps.map((st, si) => `<div class="sg-item" data-bi="${bi}" data-si="${si}" onclick="Sigilo.jump(${bi},${si})">
          <div class="sg-it"><strong>${esc(st.n)}</strong><span>${st.s} s${st.rest ? ` + ${st.rest} s` : ""}</span></div>
          <div class="m">${esc(tipOf(st))}</div></div>`).join("")}</div>`;
    }).join("");
    markList();
  }
  function markList() {
    const cur = STEPS[idx];
    document.querySelectorAll("#fuerta-app .sg-item").forEach(el =>
      el.classList.toggle("on", +el.dataset.bi === cur.bi && +el.dataset.si === cur.si));
  }

  function render() {
    const st = STEPS[idx], nx = nextWork(idx);
    const rest = STEPS.slice(idx + 1).reduce((s, x) => s + x.s, 0) + left;
    const box = $("sgTimer");
    box.classList.toggle("rest", !!st.pause && !finished);
    box.classList.toggle("soon", !!timer && left <= 3 && !finished);
    box.classList.toggle("end", finished);
    $("sgBlock").textContent = finished ? "Plan sigilo" : st.block;
    $("sgName").textContent = finished ? "¡Hecho! 30 minutos en silencio" : st.pause ? `Descanso · ahora: ${nx ? nx.n : "fin"}` : st.n;
    $("sgTip").textContent = finished ? "Bebe agua. Nadie se ha enterado." : st.pause ? (nx ? tipOf(nx) : "") : tipOf(st);
    $("sgClock").textContent = mmss(finished ? 0 : left);
    $("sgNextName").textContent = finished || !nx ? "" : st.pause ? "" : `Después: ${nx.n}`;
    $("sgLeft").textContent = `Quedan ${mmss(finished ? 0 : rest)} de ${mmss(TOTAL)}`;
    $("sgBar").style.width = `${finished ? 100 : (TOTAL - rest) / TOTAL * 100}%`;
    $("sgPlay").textContent = timer ? "Pausa" : finished ? "Empezar de nuevo" : idx || left < st.s ? "Seguir" : "Empezar";
    markList();
  }

  function tick() {
    left = Math.max(0, Math.ceil((endAt - Date.now()) / 1000));
    while (left <= 0) {
      if (idx === STEPS.length - 1) { finished = true; pause(); buzz([300, 150, 300, 150, 300]); return; }
      idx++;
      endAt += STEPS[idx].s * 1000;
      left = Math.max(0, Math.ceil((endAt - Date.now()) / 1000));
      buzz(STEPS[idx].pause ? 150 : [200, 100, 200]);
    }
    render();
  }

  async function start() {
    if (finished) { finished = false; idx = 0; left = STEPS[0].s; }
    endAt = Date.now() + left * 1000;
    timer = setInterval(tick, 250);
    // Mantener la pantalla encendida (solo si el navegador lo permite: con http en la red local puede que no).
    try { lock = await navigator.wakeLock?.request("screen"); } catch { lock = null; }
    render();
  }

  function pause() {
    clearInterval(timer); timer = null;
    try { lock?.release(); } catch {}
    lock = null;
    render();
  }

  function go(i) {
    finished = false; idx = i; left = STEPS[i].s;
    if (timer) endAt = Date.now() + left * 1000;
    render();
  }

  let ready = false;
  return {
    show() { if (!ready) { setup(); ready = true; } render(); },
    jump(bi, si) { go(STEPS.findIndex(x => x.bi === bi && x.si === si && !x.pause)); },
  };
})();
