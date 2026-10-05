@local @local_acadassistant
Feature: Global academic assistant page
  In order to ask academic questions from Moodle's main navigation
  As an authenticated personal user
  I need a global assistant page with a temporary conversation

  Scenario: An authenticated person opens the global assistant
    Given I log in as "admin"
    And I am on site homepage
    When I follow "Academic assistant"
    Then I should see "Question"
    And I should see "Send question"
    And I should see "New conversation"
    And I should see "Visible academic data comes from Moodle"
    And I should see "Write a question to start a conversation"
