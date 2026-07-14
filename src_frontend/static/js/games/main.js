const GAMES = {};

function registerGame(name, initFn) {
  GAMES[name] = initFn;
}

function loadEmployees() {
  const node = document.getElementById("employees-data");
  if (!node) return [];
  try {
    return JSON.parse(node.textContent);
  } catch (err) {
    console.error("Failed to parse employee data", err);
    return [];
  }
}

function initMounts(employees) {
  const mounts = document.querySelectorAll(".game-mount[data-game]");
  const initialized = new Set();

  function initMount(mount) {
    const name = mount.dataset.game;
    if (initialized.has(name)) return;
    const initFn = GAMES[name];
    if (!initFn) return;
    initialized.add(name);
    initFn(mount, employees);
  }

  mounts.forEach((mount) => {
    if (mount.closest(".tab-pane.active")) {
      initMount(mount);
    }
  });

  document.querySelectorAll('[data-bs-toggle="pill"]').forEach((tabButton) => {
    tabButton.addEventListener("shown.bs.tab", (event) => {
      const target = document.querySelector(event.target.dataset.bsTarget);
      const mount = target && target.querySelector(".game-mount[data-game]");
      if (mount) initMount(mount);
    });
  });
}

async function bootstrapGames() {
  const employees = loadEmployees();

  const modules = await Promise.all([
    import("./photo-match.js").catch(() => null),
    import("./two-truths.js").catch(() => null),
    import("./hobby-guess.js").catch(() => null),
    import("./guess-department.js").catch(() => null),
  ]);

  modules.forEach((mod) => {
    if (mod && typeof mod.register === "function") mod.register(registerGame);
  });

  initMounts(employees);
}

bootstrapGames();
