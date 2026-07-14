import { shuffle, avatarColorClass, el, renderScorePill, renderCompletion } from "./engine.js";

export function register(registerGame) {
  registerGame("photo-match", initPhotoMatch);
}

function initPhotoMatch(mount, employees) {
  if (!employees.length) {
    mount.innerHTML = '<p class="game-placeholder">No colleagues to match yet.</p>';
    return;
  }

  start();

  function start() {
    const avatarOrder = shuffle(employees);
    const nameOrder = shuffle(employees);
    const state = { matched: new Set(), correct: 0, streak: 0, bestStreak: 0, total: employees.length };
    let selectedAvatar = null;
    let selectedName = null;
    let locked = false;

    mount.innerHTML = "";

    const header = el("div", { className: "quiz-header" });
    header.appendChild(el("span", { className: "fw-semibold", text: "Match each colleague to their name" }));
    const scorePill = el("span", { className: "score-pill", text: renderScorePill(state) });
    header.appendChild(scorePill);
    mount.appendChild(header);

    const grid = el("div", { className: "match-grid" });
    mount.appendChild(grid);

    const avatarCol = el("div", { className: "d-flex flex-column gap-2" });
    const nameCol = el("div", { className: "d-flex flex-column gap-2" });
    grid.appendChild(avatarCol);
    grid.appendChild(nameCol);

    avatarOrder.forEach((employee) => {
      const button = el("button", { className: "match-tile", attrs: { type: "button" } });
      button.appendChild(el("span", { className: `avatar-circle-sm ${avatarColorClass(employee.color_index)}`, text: employee.initials }));
      button.addEventListener("click", () => handlePick("avatar", employee, button));
      avatarCol.appendChild(button);
    });

    nameOrder.forEach((employee) => {
      const button = el("button", { className: "match-tile", text: employee.name, attrs: { type: "button" } });
      button.addEventListener("click", () => handlePick("name", employee, button));
      nameCol.appendChild(button);
    });

    function handlePick(kind, employee, button) {
      if (locked || button.classList.contains("is-matched")) return;

      if (kind === "avatar") {
        if (selectedAvatar) selectedAvatar.button.classList.remove("is-selected");
        selectedAvatar = { employee, button };
      } else {
        if (selectedName) selectedName.button.classList.remove("is-selected");
        selectedName = { employee, button };
      }
      button.classList.add("is-selected");

      if (selectedAvatar && selectedName) evaluate();
    }

    function evaluate() {
      const avatarPick = selectedAvatar;
      const namePick = selectedName;
      const isMatch = avatarPick.employee.name === namePick.employee.name;

      if (isMatch) {
        [avatarPick.button, namePick.button].forEach((btn) => {
          btn.classList.remove("is-selected");
          btn.classList.add("is-matched");
        });
        state.matched.add(avatarPick.employee.name);
        state.correct += 1;
        state.streak += 1;
        state.bestStreak = Math.max(state.bestStreak, state.streak);
        scorePill.textContent = renderScorePill(state);
        selectedAvatar = null;
        selectedName = null;

        if (state.matched.size === state.total) {
          setTimeout(() => {
            renderCompletion(mount, {
              message: `You matched all ${state.total} colleagues, with a best streak of ${state.bestStreak} in a row.`,
              onReplay: start,
            });
          }, 350);
        }
      } else {
        locked = true;
        state.streak = 0;
        scorePill.textContent = renderScorePill(state);
        [avatarPick.button, namePick.button].forEach((btn) => btn.classList.add("is-wrong"));
        setTimeout(() => {
          [avatarPick.button, namePick.button].forEach((btn) => btn.classList.remove("is-wrong", "is-selected"));
          selectedAvatar = null;
          selectedName = null;
          locked = false;
        }, 500);
      }
    }
  }
}
