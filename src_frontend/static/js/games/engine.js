export function shuffle(items) {
  const copy = items.slice();
  for (let i = copy.length - 1; i > 0; i -= 1) {
    const j = Math.floor(Math.random() * (i + 1));
    [copy[i], copy[j]] = [copy[j], copy[i]];
  }
  return copy;
}

export function avatarColorClass(colorIndex) {
  const bucket = ((colorIndex ?? 0) % 6) + 1;
  return `avatar-color-${bucket}`;
}

export function el(tag, { className, text, html, attrs } = {}, children = []) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  if (html !== undefined) node.innerHTML = html;
  if (attrs) {
    Object.entries(attrs).forEach(([key, value]) => node.setAttribute(key, value));
  }
  children.forEach((child) => node.appendChild(child));
  return node;
}

export function renderScorePill(state) {
  return `Score: ${state.correct}/${state.total} · Streak: ${state.streak}`;
}

export function renderCompletion(container, { message, onReplay }) {
  container.innerHTML = "";
  const complete = el("div", { className: "game-complete" });
  complete.appendChild(el("h4", { className: "fw-bold mb-2", text: "Nice work!" }));
  complete.appendChild(el("p", { className: "text-muted mb-3", text: message }));
  const replay = el("button", { className: "btn btn-outline-primary", text: "Play again", attrs: { type: "button" } });
  replay.addEventListener("click", onReplay);
  complete.appendChild(replay);
  container.appendChild(complete);
}

/**
 * Generic "prompt + N choice buttons" quiz flow shared by every mode
 * that isn't pair-matching. `makeRounds()` must return a fresh array of
 * { renderPrompt(el), choices, correctIndex } — it's called again on every
 * replay so choice order/distractors reshuffle instead of repeating.
 */
export function runQuiz(container, makeRounds, { emptyMessage = "No rounds available." } = {}) {
  let rounds = makeRounds();
  if (!rounds.length) {
    container.innerHTML = `<p class="game-placeholder">${emptyMessage}</p>`;
    return;
  }

  const state = { index: 0, correct: 0, streak: 0, bestStreak: 0, total: rounds.length };

  function renderRound() {
    const round = rounds[state.index];
    container.innerHTML = "";

    const header = el("div", { className: "quiz-header" });
    header.appendChild(el("span", { text: `Question ${state.index + 1} of ${state.total}`, className: "fw-semibold" }));
    header.appendChild(el("span", { className: "score-pill", text: renderScorePill(state) }));
    container.appendChild(header);

    const promptEl = el("div", { className: "quiz-prompt" });
    container.appendChild(promptEl);
    round.renderPrompt(promptEl);

    const choicesEl = el("div", { className: "quiz-choices" });
    container.appendChild(choicesEl);

    let answered = false;
    const buttons = round.choices.map((choice, choiceIndex) => {
      const button = el("button", { className: "quiz-choice-btn", text: choice, attrs: { type: "button" } });
      button.addEventListener("click", () => {
        if (answered) return;
        answered = true;

        const isRight = choiceIndex === round.correctIndex;
        if (isRight) {
          state.correct += 1;
          state.streak += 1;
          state.bestStreak = Math.max(state.bestStreak, state.streak);
        } else {
          state.streak = 0;
        }

        buttons.forEach((btn, idx) => {
          btn.disabled = true;
          if (idx === round.correctIndex) btn.classList.add("is-correct");
          else if (idx === choiceIndex) btn.classList.add("is-incorrect");
        });

        header.querySelector(".score-pill").textContent = renderScorePill(state);
        container.appendChild(nextControl());
      });
      choicesEl.appendChild(button);
      return button;
    });
  }

  function nextControl() {
    const isLast = state.index === state.total - 1;
    const wrapper = el("div", { className: "mt-4 text-end" });
    const button = el("button", {
      className: "btn btn-primary",
      text: isLast ? "See results" : "Next question",
      attrs: { type: "button" },
    });
    button.addEventListener("click", () => {
      if (isLast) {
        renderCompletion(container, {
          message: `You scored ${state.correct} out of ${state.total}, with a best streak of ${state.bestStreak}.`,
          onReplay: () => {
            rounds = makeRounds();
            state.index = 0;
            state.correct = 0;
            state.streak = 0;
            state.total = rounds.length;
            state.bestStreak = 0;
            renderRound();
          },
        });
      } else {
        state.index += 1;
        renderRound();
      }
    });
    wrapper.appendChild(button);
    return wrapper;
  }

  renderRound();
}
