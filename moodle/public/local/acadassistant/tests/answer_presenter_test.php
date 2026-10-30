<?php
// This file is part of Moodle - http://moodle.org/
// Licensed under the GNU General Public License version 3 or later.
namespace local_acadassistant;
defined('MOODLE_INTERNAL') || die();

use local_acadassistant\local\answer_presenter;

final class answer_presenter_test extends \advanced_testcase {
    public function test_headings_items_and_due_details_render_as_accessible_blocks(): void {
        $html = answer_presenter::render(
            "Según Moodle:\n\nTareas pendientes de entrega (1)\n"
            . "• Ensayo — Historia\n  Estado: No entregada · Entrega: jueves, 29 de octubre de 2026 · 16:18"
            . "\n\nSegún los datos visibles de Moodle."
        );

        $this->assertStringContainsString('<h3 class="local-acadassistant-answer-heading">Tareas pendientes de entrega (1)</h3>', $html);
        $this->assertStringContainsString('<ul class="local-acadassistant-answer-list">', $html);
        $this->assertStringContainsString('local-acadassistant-answer-item__title">Ensayo — Historia</span>', $html);
        $this->assertStringContainsString('Estado: No entregada · Entrega: jueves, 29 de octubre de 2026 · 16:18', $html);
        $this->assertStringContainsString('local-acadassistant-answer-note--source', $html);
    }

    public function test_model_text_is_escaped_and_never_becomes_arbitrary_markup_or_links(): void {
        $html = answer_presenter::render(
            "Respuesta: <img src=x onerror=alert(1)>\n[enlace](javascript:alert(1))"
        );

        $this->assertStringContainsString('&lt;img src=x onerror=alert(1)&gt;', $html);
        $this->assertStringContainsString('[enlace](javascript:alert(1))', $html);
        $this->assertStringNotContainsString('<img', $html);
        $this->assertStringNotContainsString('href=', $html);
    }
}
