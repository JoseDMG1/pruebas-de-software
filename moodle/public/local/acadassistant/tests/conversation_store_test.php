<?php
// This file is part of Moodle - http://moodle.org/
//
// Moodle is free software: you can redistribute it and/or modify
// it under the terms of the GNU General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.

namespace local_acadassistant;

defined('MOODLE_INTERNAL') || die();

/** Tests session-only conversation state through its public operations. */
final class conversation_store_test extends \advanced_testcase {
    public function test_follow_up_does_not_reuse_document_reference_numbers_from_an_earlier_answer(): void {
        $this->resetAfterTest();
        $this->setUser($this->getDataGenerator()->create_user());
        $store = new \local_acadassistant\local\conversation_store();
        $store->append('¿Cuándo inicia el ciclo?', 'En agosto. [4]', []);

        $this->assertSame('En agosto.', $store->context_for_question('¿Y qué fecha exacta?')[0]['answer']);
        $this->assertSame('En agosto. [4]', $store->messages()[0]['answer']);
    }

    public function test_follow_up_context_is_session_scoped_and_new_conversation_clears_it(): void {
        $this->resetAfterTest();
        $firstuser = $this->getDataGenerator()->create_user();
        $seconduser = $this->getDataGenerator()->create_user();
        $store = new \local_acadassistant\local\conversation_store();

        $this->setUser($firstuser);
        $store->append('¿Cuándo inicia el segundo ciclo?', 'En agosto.', []);
        $this->assertSame('¿Cuándo inicia el segundo ciclo?', $store->context()[0]['question']);
        for ($index = 2; $index <= 5; $index++) {
            $store->append('Pregunta ' . $index, 'Respuesta ' . $index, []);
        }
        $this->assertCount(3, $store->context());
        $this->assertSame('Pregunta 3', $store->context()[0]['question']);
        $store->append('¿Qué calendario consultaste?', 'Calendario Moodle.', [], ['calendar']);
        $this->assertSame(['calendar'], $store->messages()[5]['academic_sources']);

        $this->setUser($seconduser);
        $this->assertSame([], $store->context());

        $this->setUser($firstuser);
        $store->clear();
        $this->assertSame([], $store->context());
        $this->assertSame([], $store->messages());
    }

    public function test_only_explicit_follow_ups_receive_context_after_a_topic_change(): void {
        $this->resetAfterTest();
        $user = $this->getDataGenerator()->create_user();
        $this->setUser($user);
        $store = new \local_acadassistant\local\conversation_store();

        $store->append('¿Qué tareas tengo pendientes en Álgebra?', 'Una tarea.', [], [], true);
        $this->assertSame([], $store->context_for_question('¿Cuánto cuesta el duplicado de carné?'));
        $store->append('¿Cuánto cuesta el duplicado de carné?', 'Consulta documentos institucionales.', [], [], true);
        $this->assertSame([], $store->context_for_question('¿Cuándo inicia el segundo ciclo?'));

        $store->append('¿Cuándo inicia el segundo ciclo?', 'En agosto.', [], [], true);
        $this->assertSame(
            [['question' => '¿Cuándo inicia el segundo ciclo?', 'answer' => 'En agosto.']],
            $store->context_for_question('¿Y qué fecha exacta?')
        );
    }

    public function test_moodle_logout_discards_context_before_the_user_logs_in_again(): void {
        global $SESSION;

        $this->resetAfterTest();
        $user = $this->getDataGenerator()->create_user();
        $this->setUser($user);
        $store = new \local_acadassistant\local\conversation_store();
        $store->append('¿Cuándo inicia el ciclo?', 'En agosto.', []);

        require_logout();
        $this->assertFalse(isloggedin());
        $this->assertFalse(property_exists($SESSION, 'local_acadassistant_conversation'));
        $this->assertSame([], $store->messages());

        $this->setUser($user);
        $this->assertSame([], $store->messages());
        $this->assertSame([], $store->context_for_question('¿Y qué fecha exacta?'));
    }

    public function test_context_is_not_shared_when_identity_changes_in_the_active_session(): void {
        $this->resetAfterTest();
        $firstuser = $this->getDataGenerator()->create_user();
        $seconduser = $this->getDataGenerator()->create_user();
        $this->setUser($firstuser);
        $store = new \local_acadassistant\local\conversation_store();
        $store->append('¿Qué tareas tengo pendientes?', 'Tienes una tarea.', []);

        \core\session\manager::set_user($seconduser);
        $this->assertSame([], $store->messages());

        \core\session\manager::set_user($firstuser);
        $this->assertSame([], $store->context_for_question('¿Y cuándo vence?'));
    }

    public function test_new_moodle_session_after_expiration_cannot_restore_context(): void {
        global $SESSION;

        $this->resetAfterTest();
        $user = $this->getDataGenerator()->create_user();
        $this->setUser($user);
        $store = new \local_acadassistant\local\conversation_store();
        $store->append('¿Cuándo inicia el ciclo?', 'En agosto.', []);

        // Moodle replaces the session payload when a session expires; model that boundary here.
        \core\session\manager::init_empty_session();
        $this->assertFalse(property_exists($SESSION, 'local_acadassistant_conversation'));
        $this->assertSame([], $store->messages());

        $this->setUser($user);
        $this->assertSame([], $store->messages());
        $this->assertSame([], $store->context_for_question('¿Y qué fecha exacta?'));
    }
    public function test_continuation_is_private_temporary_and_does_not_restore(): void {
        $this->resetAfterTest();
        $this->setUser($this->getDataGenerator()->create_user());
        $store = new \local_acadassistant\local\conversation_store();
        $cursor = ['question' => '¿Qué materias llevo?', 'seen' => ['courses:123']];
        $store->append('¿Qué materias llevo?', 'Una lista parcial.', [], [], true, $cursor);
        $this->assertSame($cursor, $store->continuation());
        $this->assertTrue($store->is_follow_up('continúa'));
        $store->clear();
        $this->assertNull($store->continuation());
        $store->append('cursos', 'Lista parcial.', [], [], true, $cursor);
        $this->setUser($this->getDataGenerator()->create_user());
        $this->assertNull($store->continuation());
    }
    public function test_unanswered_clarification_does_not_capture_a_new_topic(): void {
        $this->resetAfterTest();
        $this->setUser($this->getDataGenerator()->create_user());
        $store = new \local_acadassistant\local\conversation_store();
        $store->append('¿Cuándo vence esa tarea en Biologia 102?',
            '¿De cuál tarea necesitas la fecha? Indica su nombre y curso.', []);
        $this->assertFalse($store->is_follow_up('¿Qué cursos tengo?'));
        $this->assertSame([], $store->context_for_question('¿Qué cursos tengo?'));
        $this->assertFalse($store->is_follow_up('¿Cuánto pago?'));
        $this->assertTrue($store->is_follow_up('Informe de laboratorio'));
    }
}
