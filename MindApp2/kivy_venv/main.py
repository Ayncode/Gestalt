from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.screenmanager import Screen, ScreenManager
from kivy.app import App
from kivy.core.window import Window
from kivy.uix.image import Image
import openai
import boto3
from botocore.exceptions import ClientError
from kivy.uix.popup import Popup

import os
from dotenv import load_dotenv

load_dotenv()

config = {
    'aws_access_key_id': os.getenv('AWS_ACCESS_KEY_ID'),
    'aws_secret_key': os.getenv('AWS_SECRET_KEY'),
    'open_ai_api_key': os.getenv('OPEN_AI_API_KEY')
}

aws_access_key = config['aws_access_key_id']
aws_secret_key = config['aws_secret_key']

aws_region = 'us-east-1'


cognito_client = boto3.client('cognito-idp', aws_access_key_id=aws_access_key, aws_secret_access_key=aws_secret_key, region_name=aws_region)
s3_client = boto3.client('s3', aws_access_key_id=aws_access_key, aws_secret_access_key=aws_secret_key, region_name=aws_region)

openai.api_key = config['open_ai_api_key']
modelT = 'gpt-3.5-turbo'
chat_history = []
current_user = ''


class ChatScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # Load chat history from a text file when the screen is opened

        layout = BoxLayout(orientation='vertical')

        # Chat history (center part) using ScrollView and reversed BoxLayout
        chat_history_layout = BoxLayout(orientation='vertical', spacing=5, size_hint_y=None)
        chat_history_layout.bind(minimum_height=chat_history_layout.setter('height'))

        chat_history_scroll_view = ScrollView()
        chat_history_scroll_view.add_widget(chat_history_layout)

        layout.add_widget(chat_history_scroll_view)

        # User input and send button (right part)
        user_input_layout = BoxLayout(orientation='horizontal', size_hint=(1, None), height=50)

        user_input = TextInput(multiline=False, font_size=20, hint_text = "Talk about your day...")
        user_input_layout.add_widget(user_input)

        send_button = Button(text='Send', size_hint=(None, None), size=(100, 50), font_size=20,
                             on_press=lambda x: self.send_message(chat_history_layout, user_input.text, user_input))
        user_input.text = ''
        user_input_layout.add_widget(send_button)

        layout.add_widget(user_input_layout)

        # Exit button
        exit_button = Button(text='Exit', size_hint=(None, None), size=(100, 50), font_size=20,
                             on_press=lambda x: self.switch_to_dashboard())
        layout.add_widget(exit_button)

        self.add_widget(layout)

    def load_chat_history(self):
        try:
            response = s3_client.get_object(Bucket='gestaltfilestorage', Key=f'{current_user}ChatHistory.txt')
            lines = response['Body'].read().decode('utf-8').splitlines()
            for line in lines:
                if line.startswith('You: '):
                    user_message = {"role": "user", "content": line[5:]}
                    chat_history.append(user_message)
                elif line.startswith('Bot: '):
                    bot_message = {"role": "assistant", "content": line[5:]}
                    chat_history.append(bot_message)
            print(chat_history)
        except ClientError as e:
            print(f"Error loading chat history from S3: {e}")

    def send_message(self, chat_history_layout, message, user_input):
        # Append user message to chat history
        user_message = {"role": "user", "content": message}
        chat_history.append(user_message)

        # Append user message to chat history
        user_message_text = f'You: {message}\n'
        chat_label = Label(text=user_message_text, font_size=20, halign='right', size_hint_y=None,
                           text_size=(self.width, None))
        chat_label.size_hint_y = None
        chat_label.bind(texture_size=chat_label.setter('size'))
        chat_history_layout.add_widget(chat_label)

        user_input.text = ''

        # Generate chatbot's response using GPT-2
        bot_response = self.generate_response(chat_history)

        # Append chatbot's response to chat history
        bot_message = f'Bot: {bot_response}\n'
        bot_chat_label = Label(text=bot_message, font_size=20, halign='left', size_hint_y=None,
                               text_size=(self.width, None))
        bot_chat_label.size_hint_y = None
        bot_chat_label.bind(texture_size=bot_chat_label.setter('size'))
        chat_history_layout.add_widget(bot_chat_label)

        # Save the entire chat dialogue to a text file
        self.save_chat_history(chat_history)

        # Scroll to the bottom only if already at the bottom
        chat_history_scroll_view = chat_history_layout.parent
        if chat_history_scroll_view.scroll_y == 0:
            chat_history_scroll_view.scroll_y = 0

        # Trigger layout update to prevent messages from sliding upwards
        chat_history_layout.do_layout()

        # Adjust the chat history layout to display the latest messages at the bottom
        chat_history_layout.height = sum(label.height for label in chat_history_layout.children) + (
                len(chat_history_layout.children) - 1) * chat_history_layout.spacing

    def save_chat_history(self, chat_hist):
        try:
            # Save the entire chat history to a string

            chat_history_str = ''
            for message in chat_hist:
                if message["role"] == "user":
                    chat_history_str += f'You: {message["content"]}\n'
                elif message["role"] == "assistant":
                    chat_history_str += f'Bot: {message["content"]}\n'

            # Delete the existing ChatHistory.txt file in S3
            s3_client.delete_object(Bucket='gestaltfilestorage', Key=f'{current_user}ChatHistory.txt')

            # Upload the updated chat history to S3
            s3_client.put_object(Bucket='gestaltfilestorage', Key=f'{current_user}ChatHistory.txt',
                                 Body=chat_history_str)
        except ClientError as e:
            print(f"Error saving chat history to S3: {e}")

    def generate_response(self, chat_history):

       # Format chat history for OpenAI API
       instructions = "You are a therapist and the user is having a session with you.\
       Also, if someone is stressed about a workload, suggest the To-Do list feature in the Gestalt app(which you are an element of. \
       Give more advice rather than asking questions, although questions are ok. \
       Try to make your responses concise and don't use lists unless absolutely neccesary. Also, make sure you help the patiend to cognitively reframe things stressing them out. analyze their behaviors such that you can help them to rethink the way they think. The goal is to help them for long periods of time, not just short term relief.  "

       messages = [{"role": "system", "content": instructions}]
       messages.extend(chat_history)  # Include user and assistant messages

       # Generate chatbot's response using OpenAI ChatCompletion model
       response = openai.ChatCompletion.create(
           model="gpt-3.5-turbo",
           messages= messages
       )
       chat_history.append({"role": "assistant", "content": response.choices[0].message['content'].strip()})
       return response.choices[0].message['content'].strip()


    def switch_to_dashboard(self):
       self.manager.current = 'dashboard'


class ToDoScreen(Screen):
  def __init__(self, **kwargs):
      super(ToDoScreen, self).__init__(**kwargs)
      self.todo_list = []

      layout = BoxLayout(orientation='vertical', spacing=10, padding=10, size_hint=(1, 1),
                         pos_hint={'center_x': 0.5, 'center_y': 0.5})

      exit_button = Button(text="Exit", size_hint=(None, None), width=100, height=50)
      exit_button.bind(on_press=lambda x: self.switch_to_dashboard())

      self.task_input = TextInput(hint_text="Enter a task", size_hint=(1, None), height=50)
      add_button = Button(text="Add Task", size_hint=(1, None), height=50)  # Adjusted size
      add_button.bind(on_press=self.add_task)

      # Create a ScrollView
      task_container_scrollview = ScrollView()

      # Create a new BoxLayout for the task_container with reversed orientation
      self.task_container = BoxLayout(orientation='vertical', spacing=5, size_hint_y=None, padding=5)

      task_container_scrollview.add_widget(self.task_container)

      layout.add_widget(exit_button)
      layout.add_widget(self.task_input)
      layout.add_widget(add_button)
      layout.add_widget(task_container_scrollview)  # Add the ScrollView

      self.add_widget(layout)


  def add_task_to_list(self, task_text):
      task_layout = BoxLayout(orientation='horizontal', spacing=5, size_hint_y=None, height=30)
      task_label = Label(text=task_text)
      remove_button = Button(text="Remove")
      remove_button.bind(on_press=lambda x: self.remove_task(task_layout, task_text))
      task_layout.add_widget(task_label)
      task_layout.add_widget(remove_button)

      # Insert new tasks at the top
      self.task_container.add_widget(task_layout, index=0)
      self.todo_list.append(task_text)

      # Update the height of the task container for scrolling
      self.task_container.height += task_layout.height
      self.save_tasks_to_s3()

  def add_task(self, instance):
      task_text = self.task_input.text
      if task_text:
          self.add_task_to_list(task_text)
          self.save_tasks_to_s3()
          self.task_input.text = ""

  def remove_task(self, task_layout, task_text):
      if task_text in self.todo_list:
          self.todo_list.remove(task_text)
      self.task_container.remove_widget(task_layout)
      self.task_container.height -= task_layout.height
      self.save_tasks_to_s3()

  def load_tasks_from_s3(self):
      print("current user load: " + current_user)
      try:

          response = s3_client.get_object(Bucket='gestaltfilestorage', Key=f'{current_user}ToDoList.txt')
          tasks = response['Body'].read().decode('utf-8').splitlines()
          for task in tasks:
              if task:
                  self.add_task_to_list(task)
      except ClientError as e:
          print(f"Error loading tasks from S3: {e}")

  def save_tasks_to_s3(self):
      try:
          # Save current tasks to a data structure
          current_tasks = '\n'.join(self.todo_list)
          print("current user save: " + current_user)
          # Delete the existing ToDoList.txt file in S3
          s3_client.delete_object(Bucket='gestaltfilestorage', Key=f'{current_user}ToDoList.txt')

          # Upload the updated tasks to S3
          s3_client.put_object(Bucket='gestaltfilestorage', Key=f'{current_user}ToDoList.txt',
                               Body=current_tasks)
      except ClientError as e:
          print(f"Error saving tasks to S3: {e}")

  def switch_to_dashboard(self):
      self.manager.current = 'dashboard'


class LoginScreen(Screen):

 def __init__(self, **kwargs):
     super().__init__(**kwargs)
     print(aws_access_key, aws_secret_key, config['open_ai_api_key'])
     layout = BoxLayout(orientation='vertical', spacing=10)
     layout.size_hint = (0.75, 0.75)
     layout.pos_hint = {'center_x': 0.5, 'center_y': 0.5}

     img = Image(source='GestaltLogoFinal2.PNG', height =(600))
     layout.add_widget(img)

     username_label = Label(text='Username:', size_hint_y=None, height=30)
     self.username_input = TextInput(multiline=False, size_hint_y=None, height=30)

     password_label = Label(text='Password:', size_hint_y=None, height=30)
     self.password_input = TextInput(password=True, multiline=False, size_hint_y=None, height=30)

     login_button = Button(text='Login', on_press=self.login, size_hint_y=None, height=30)
     sign_up_button = Button(text='Sign Up', on_press=lambda x: self.sign_up(), size_hint_y=None, height=30)

     layout.add_widget(username_label)
     layout.add_widget(self.username_input)
     layout.add_widget(password_label)
     layout.add_widget(self.password_input)
     layout.add_widget(login_button)
     layout.add_widget(sign_up_button)

     self.add_widget(layout)

 def login(self, instance):
     global current_user
     username = self.username_input.text
     password = self.password_input.text
     current_user = username
     print("current user: " + current_user)
     if self.cognito_login(username, password):
         # Navigate to the dashboard on successful login
         self.manager.current = 'dashboard'

     else:
         # Display an error message in a popup on login failure
         popup = Popup(title='Login Error', content=Label(text='Invalid username or password.'),
                       size_hint=(None, None), size=(200, 200))
         popup.open()

 def cognito_login(self, username, password):
     try:
         response = cognito_client.initiate_auth(
             ClientId='3rscvq1mrc51g92831osg1sgr7',
             AuthFlow='USER_PASSWORD_AUTH',
             AuthParameters={
                 'USERNAME': username,
                 'PASSWORD': password,
             },
         )
         return True
     except ClientError as e:
         print(f"Error during login: {e.response['Error']['Message']}")
         return False

 def sign_up(self):
     global current_user
     username = self.username_input.text
     password = self.password_input.text
     self.username = username
     current_user = username

     if self.cognito_sign_up(username, password):
         # Display a popup for entering the confirmation code
         self.show_verification_popup()

     else:
         # Display an error message in a popup on sign-up failure
         popup = Popup(title='Sign-Up Error',
                       content=Label(text='Failed to sign up.\nPlease check your input and try again.'),
                       size_hint=(None, None), size=(200, 200))
         popup.open()

 def show_verification_popup(self):
     # Create a popup with a TextInput for entering the verification code
     verification_input = TextInput(hint_text='Enter verification code', multiline=False)
     verification_popup = Popup(title='Verification Code',
                                content=BoxLayout(orientation='vertical'),
                                size_hint=(None, None), size=(200, 200),
                                auto_dismiss=False)

     # Create a button to confirm the verification code
     confirm_button = Button(text='Confirm',
                             on_press=lambda x: self.confirm_signup(verification_input.text, verification_popup))
     verification_popup.content.add_widget(confirm_button)

     # Create a button to dismiss the popup
     dismiss_button = Button(text='Dismiss', on_press=verification_popup.dismiss)
     verification_popup.content.add_widget(dismiss_button)

     # Add the verification input to the popup content
     verification_popup.content.add_widget(verification_input)

     verification_popup.open()


 def cognito_sign_up(self, username, password):
     current_user = username
     try:
         response = cognito_client.sign_up(
             ClientId='3rscvq1mrc51g92831osg1sgr7',
             Username=username,
             Password=password,
             UserAttributes=[
                 {'Name': 'email', 'Value': username},
             ],
         )
         print("Sign-up successful. Confirmation code sent to:", response['UserConfirmed'])
         current_user = self.username

         s3_client.put_object(Bucket='gestaltfilestorage', Key=f'{self.username}ToDoList.txt',
                              Body='')

         s3_client.put_object(Bucket='gestaltfilestorage', Key=f'{self.username}ChatHistory.txt',
                              Body='')

         return True

     except ClientError as e:
         print(f"Error during sign-up: {e.response['Error']['Message']}")
         return False



 def confirm_signup(self, verification_code, verification_popup):
     try:
         response = cognito_client.confirm_sign_up(
             ClientId='3rscvq1mrc51g92831osg1sgr7',
             Username=self.username,
             ConfirmationCode=verification_code,
         )
         print("Account confirmed successfully.")
         verification_popup.dismiss()

         # Optionally, you can navigate to the dashboard or perform other actions after confirmation
         self.manager.current = 'dashboard'

     except ClientError as e:
         print(f"Error confirming signup: {e.response['Error']['Message']}")
         # Display an error message in the popup on confirmation failure
         error_label = Label(text=f'Error: {e.response["Error"]["Message"]}')
         verification_popup.content.add_widget(error_label)




class DashboardScreen(Screen):
   Window.clearcolor = (30/255,129/255,176/255,0)
   def __init__(self, **kwargs):
       super().__init__(**kwargs)

       layout = BoxLayout(orientation='vertical', spacing=10,)
       layout.pos_hint = {'center_x': 0.5, 'center_y': 0.5}

       #Dashboard
       img = Image(source = 'GestaltLogoFinal2.PNG', size = (300, 300))
       layout.add_widget(img)

       chat_button = Button(
           text='Therapist',
           size_hint=(1, 0.5),
           size=(200, 50),
           font_size=20,
           on_release=lambda x: self.load_and_switch_to_chat()
       )
       layout.add_widget(chat_button)

       # To-Do List button
       todo_list_button = Button(
           text='To-Do List',
           size_hint=(1, 0.5),
           size=(200, 50),
           font_size=20,
           on_release=lambda x: self.load_and_switch_to_todo_list()
       )
       layout.add_widget(todo_list_button)

       exit_button = Button(
           text='Exit',
           size_hint=(1, 0.5),
           size=(200, 50),
           font_size=20,
           background_color = (1, 0, 0),
           on_release=lambda x: exit()
       )
       layout.add_widget(exit_button)


       self.add_widget(layout)


   def load_and_switch_to_todo_list(self):
       todo_screen = self.manager.get_screen('todo')

       todo_screen.load_tasks_from_s3()
       self.switch_screen('todo')

   def load_and_switch_to_chat(self):
       chat_screen = self.manager.get_screen('chat')
       popup = Popup(title='Disclaimer', content=Label(text='This app is not meant to \nsubstitute medical advice.'),
                     size_hint=(None, None), size=(200, 200))
       popup.open()

       chat_screen.load_chat_history()
       self.switch_screen('chat')

   def switch_screen(self, screen_name):
       self.manager.current = screen_name

class MyApp(App):
   def build(self):
       # Create the ScreenManager
       sm = ScreenManager()

       # Add screens to the ScreenManager
       sm.add_widget(LoginScreen(name='login'))
       sm.add_widget(DashboardScreen(name='dashboard'))
       sm.add_widget(ChatScreen(name='chat'))
       sm.add_widget(ToDoScreen(name='todo'))

       return sm

   def on_start(self):
       chat_screen = self.root.get_screen('chat')
       chat_screen.chat_history = chat_history


if __name__ == '__main__':
   MyApp().run()