# 04 — Formulários e aprovações

**Catálogo de operações:** `rename_label`, `set_help`, `add_field`, `set_options`, `set_required`, `add_attachment`, `add_conditional_attachment`, `add_validation`, `deactivate_field`, `add_section`, `move_field`. Exclusão física é `unsupported`; oferecer `deactivate_field`.

**Condições:** `eq neq in gt gte lt lte exists and or not`. Ausente/nulo => falso. Sem coerção texto/número.

**Testes.** Cada regra nova exige exemplo positivo, negativo e de limite quando aplicável. Mudança de rótulo exige comparação do resultado esperado. Uma pessoa revisa o resultado esperado; sugestão do mesmo LLM não é validação independente.

**Aprovação (backend).** Municipal e Aprova, por atores distintos com papel no servidor, sobre a mesma candidata (hash), suíte (hash) e execução. Editar candidata/testes ou receber evidência contraditória invalida as duas.

**Aplicação.** Compare-and-swap do ponteiro vigente contra a versão-base; recibo único; read-back com testes; só então nota interna e fechamento.
