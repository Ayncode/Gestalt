import kivy
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.lang import Builder
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.label import Label
# from chatterbot import ChatBot
from kivymd.app import MDApp

# from kivymd.uix.navigationdrawer import NavigationLayout

kivy.require('1.11.1')


class ChatBotApp(MDApp):
    def build(self):
        # self.chatbot = ChatBot()

        layout = BoxLayout(orientation='horizontal')

        builder = Builder.load_file("navbar.kv")
        # Navigation bar (on the left side)
        navigation_bar = Builder.load_string('''NavigationBar:
        id: nav_bar''')
        layout.add_widget(navigation_bar)

        # Chat history (center part)
        self.chat_history = TextInput(readonly=True, font_size=20, background_color=(0.9, 0.9, 0.9, 1.0))
        scroll_view = ScrollView()
        scroll_view.add_widget(self.chat_history)
        layout.add_widget(scroll_view)

        # User input and send button (right part)
        user_input_layout = BoxLayout(orientation='vertical', size_hint_x=0.7)

        user_input = TextInput(multiline=False, font_size=20, background_color=(0.7, 0.7, 0.7, 1.0))
        user_input_layout.add_widget(user_input)

        send_button = Button(text='Send', on_press=lambda x: self.send_message(user_input.text))
        user_input_layout.add_widget(send_button)

        layout.add_widget(user_input_layout)

        return layout

    def send_message(self, message):
        # Clear user input
        self.root.children[2].children[0].text = ''

        # Append user message to chat history
        self.chat_history.text += f'You: {message}\n'

        # Get chatbot response
        # bot_response = self.chatbot.get_response(message)

        # Append chatbot's response to chat history
        self.chat_history.text += f'Bot: {"bot_response"}\n'

        # Scroll to the bottom
        self.root.children[1].scroll_y = 0

    def navigate(self, option):
        pass

    def on_start(self):
        # Welcome message from the chatbot
        welcome_message = "Hi! I'm your chatbot assistant. How can I help you today?"
        self.chat_history.text += f'Bot: {welcome_message}\n'


if __name__ == '__main__':
    ChatBotApp().run()