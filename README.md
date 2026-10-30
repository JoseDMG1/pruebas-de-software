# Asistente académico — Universidad del Valle

Asistente integrado en Moodle para consultar documentos institucionales, cursos,
docentes, tareas, entregas, notas y calendario, y abrir destinos autorizados mediante
lenguaje natural. Usa DeepSeek para el chat y Gemini para embeddings.

- [Guía de presentación, perfiles, configuración y pruebas](docs/presentacion-asistente.md)
- [Operación local de Moodle](docs/pruebas-locales-sprint-2.md)
- [API RAG y configuración técnica](rag-service/README.md)
- [Validación histórica del 22 de octubre](docs/validacion-deepseek.md)
- [Validación de rúbrica del 29 de octubre](docs/validacion-rubrica-final.md)
- [Resultados de evaluación DeepSeek](rag-service/docs/evaluation-deepseek-results.json)
- [Modelo de dominio](GLOSSARY.md) y [autorización de datos](docs/adr/0001-moodle-autoriza-datos-academicos.md)
- [Entrega corregida y evidencias de la rúbrica](<informe y rúbrica/corregido/GUIA-DE-ENTREGA.md>)
- [Scripts de validación y generación de entregables](dev/validation/README.md)

## Inicio local

Configura `DEEPSEEK_API_KEY` y `GEMINI_API_KEY` en `rag-service/.env` siguiendo
`rag-service/.env.example`. Desde esta raíz:

```bash
bash dev/moodle/up.sh
```

Abre <http://127.0.0.1:8088/local/acadassistant/index.php>. Las credenciales se generan
en `.local/sprint2-credentials.md`, excluido de Git.

El entorno se publica únicamente en localhost. El generador prepara contenido de
presentación y debe ejecutarse sobre esta instalación local, sin datos de un campus real.
Las claves permanecen en el servidor; Moodle aplica los permisos de cada cuenta.
