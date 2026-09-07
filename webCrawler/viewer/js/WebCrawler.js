const summary = document.getElementById("summary");
const domain = document.getElementById("domain");
const totalResults = document.getElementById("total-results");
const message = document.getElementById("message");
const resultsContainer = document.getElementById("results-container");
const resultsBody = document.getElementById("results-body");


function getResultPath() {
  const params = new URLSearchParams(window.location.search);
  return params.get("result");
}


function createResultRow(result, index) {
  const row = document.createElement("tr");

  const numberCell = document.createElement("td");
  numberCell.textContent = index + 1;

  const termCell = document.createElement("td");
  termCell.textContent = result.term || "";

  const urlCell = document.createElement("td");
  const link = document.createElement("a");
  link.href = result.url || "#";
  link.textContent = result.url || "";
  link.target = "_blank";
  link.rel = "noopener noreferrer";
  urlCell.appendChild(link);

  const sourceCell = document.createElement("td");
  sourceCell.textContent = result.source || "";

  row.appendChild(numberCell);
  row.appendChild(termCell);
  row.appendChild(urlCell);
  row.appendChild(sourceCell);

  return row;
}


function renderResults(data) {
  const results = Array.isArray(data.results) ? data.results : [];

  domain.textContent = data.domain || "";
  totalResults.textContent = data.total_results ?? results.length;
  summary.hidden = false;

  if (!results.length) {
    message.textContent = "No results found.";
    return;
  }

  resultsBody.replaceChildren();

  results.forEach((result, index) => {
    resultsBody.appendChild(
      createResultRow(result, index)
    );
  });

  message.hidden = true;
  resultsContainer.hidden = false;
}


function showError(text) {
  summary.hidden = true;
  resultsContainer.hidden = true;
  message.hidden = false;
  message.textContent = text;
}


async function loadResults() {
  const resultPath = getResultPath();

  if (!resultPath) {
    showError("No result file specified.");
    return;
  }

  try {
    const response = await fetch(`../${resultPath}`);

    if (!response.ok) {
      throw new Error(
        `HTTP ${response.status}`
      );
    }

    const data = await response.json();
    renderResults(data);
  } catch (error) {
    console.error(error);
    showError("Unable to load crawler results.");
  }
}


loadResults();