import { shuffle, runQuiz, el } from "./engine.js";

export function register(registerGame) {
  registerGame("hobby-guess", (mount, employees) => {
    runQuiz(mount, () => buildRounds(employees), { emptyMessage: "No hobbies to guess from yet." });
  });
}

function buildRounds(employees) {
  const candidates = employees.filter((employee) => employee.hobbies?.length);
  if (candidates.length < 2) return [];

  return shuffle(candidates).map((employee) => {
    const others = employees.filter((other) => other.name !== employee.name);
    const distractors = shuffle(others).slice(0, Math.min(3, others.length));
    const choiceEmployees = shuffle([employee, ...distractors]);
    const emoji = employee.hobbies.map((hobby) => hobby.emoji).join("  ");

    return {
      renderPrompt(promptNode) {
        promptNode.appendChild(el("p", { className: "mb-1 fs-3", text: emoji }));
        promptNode.appendChild(el("p", { className: "text-muted mb-0", text: "Whose hobbies are these?" }));
      },
      choices: choiceEmployees.map((choice) => choice.name),
      correctIndex: choiceEmployees.findIndex((choice) => choice.name === employee.name),
    };
  });
}
