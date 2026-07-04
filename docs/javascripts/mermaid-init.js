(function () {
  function preferredTheme() {
    return document.body.getAttribute("data-md-color-scheme") === "slate"
      ? "dark"
      : "default";
  }

  async function renderMermaid() {
    if (!window.mermaid) {
      return;
    }

    var diagrams = Array.from(
      document.querySelectorAll(
        ".mermaid:not([data-processed]):not([data-mermaid-rendering])"
      )
    );

    if (diagrams.length === 0) {
      return;
    }

    window.mermaid.initialize({
      startOnLoad: false,
      theme: preferredTheme(),
      securityLevel: "strict",
    });

    diagrams.forEach(function (diagram) {
      diagram.setAttribute("data-mermaid-rendering", "true");
    });

    try {
      await window.mermaid.run({ nodes: diagrams });
    } catch (error) {
      var rendered = diagrams.some(function (diagram) {
        return diagram.querySelector("svg");
      });
      if (!rendered) {
        console.warn("Mermaid diagrams did not render", error);
      }
    } finally {
      diagrams.forEach(function (diagram) {
        diagram.removeAttribute("data-mermaid-rendering");
      });
    }
  }

  if (window.document$ && typeof window.document$.subscribe === "function") {
    window.document$.subscribe(renderMermaid);
  } else {
    document.addEventListener("DOMContentLoaded", renderMermaid);
  }
})();
