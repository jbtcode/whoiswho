import { shuffle, runQuiz, el } from "./engine.js";

export function register(registerGame) {
  registerGame("two-truths", (mount, employees) => {
    runQuiz(mount, () => buildRounds(employees), { emptyMessage: "No colleague facts available yet." });
  });
}

function buildRounds(employees) {
  const candidates = employees.filter((employee) => employee.two_truths && employee.two_truths.statements?.length === 3);

  return shuffle(candidates).map((employee) => {
    const { statements, lie_index: lieIndex } = employee.two_truths;
    const shuffledStatements = shuffle(statements.map((text, index) => ({ text, isLie: index === lieIndex })));

    return {
      renderPrompt(promptNode) {
        promptNode.appendChild(el("p", { className: "mb-0", text: `Which statement about ${employee.name} is the lie?` }));
      },
      choices: shuffledStatements.map((s) => s.text),
      correctIndex: shuffledStatements.findIndex((s) => s.isLie),
    };
  });
}
