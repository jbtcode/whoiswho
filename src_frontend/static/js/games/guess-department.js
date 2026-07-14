import { shuffle, runQuiz, el } from "./engine.js";

export function register(registerGame) {
  registerGame("guess-department", (mount, employees) => {
    runQuiz(mount, () => buildRounds(employees), { emptyMessage: "Not enough departments to quiz on yet." });
  });
}

function redactName(summary, name) {
  return summary ? summary.split(name).join("This colleague") : summary;
}

function buildRounds(employees) {
  const departments = [...new Set(employees.map((employee) => employee.department).filter(Boolean))];
  const candidates = employees.filter((employee) => employee.summary && employee.department);
  if (departments.length < 2 || !candidates.length) return [];

  return shuffle(candidates).map((employee) => {
    const otherDepartments = departments.filter((department) => department !== employee.department);
    const distractors = shuffle(otherDepartments).slice(0, Math.min(3, otherDepartments.length));
    const choiceDepartments = shuffle([employee.department, ...distractors]);

    return {
      renderPrompt(promptNode) {
        promptNode.appendChild(el("p", { className: "mb-0", text: redactName(employee.summary, employee.name) }));
      },
      choices: choiceDepartments,
      correctIndex: choiceDepartments.findIndex((department) => department === employee.department),
    };
  });
}
