#!/bin/bash
# Lanceur de l'outil YamHub — règle le chemin des librairies WeasyPrint (macOS/Homebrew)
# puis démarre Streamlit. Usage :  chmod +x run.sh && ./run.sh
cd "$(dirname "$0")"
[ -d .venv ] && source .venv/bin/activate
# Chemin des libs Homebrew (pango/gobject) pour WeasyPrint
if command -v brew >/dev/null 2>&1; then
  export DYLD_FALLBACK_LIBRARY_PATH="$(brew --prefix)/lib:${DYLD_FALLBACK_LIBRARY_PATH}"
fi
echo "Vérif WeasyPrint :"
python3 -c "import weasyprint; print('  WeasyPrint OK')" || {
  echo "  -> WeasyPrint ne trouve pas ses librairies. Fais : brew install pango"
  echo "     puis vérifie : ls \$(brew --prefix)/lib/libgobject-2.0*"
}
streamlit run app.py
