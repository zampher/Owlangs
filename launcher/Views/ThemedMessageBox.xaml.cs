using System.Windows;

namespace OwlangsLauncher.Views
{
    public partial class ThemedMessageBox : Window
    {
        public MessageBoxResult Result { get; private set; } = MessageBoxResult.Cancel;

        public ThemedMessageBox()
        {
            InitializeComponent();
        }

        public static MessageBoxResult Show(Window? owner, string message, string title = "Confirm", MessageBoxButton buttons = MessageBoxButton.YesNo, MessageBoxImage icon = MessageBoxImage.Question)
        {
            var dialog = new ThemedMessageBox
            {
                Owner = owner,
                Title = title
            };
            
            dialog.TitleTextBlock.Text = title;
            dialog.MessageTextBlock.Text = message;

            // Configure buttons based on MessageBoxButton
            if (buttons == MessageBoxButton.OK)
            {
                dialog.YesButton.Content = "OK";
                dialog.YesButton.Click += (s, e) => { dialog.Result = MessageBoxResult.OK; dialog.Close(); };
                dialog.NoButton.Visibility = Visibility.Collapsed;
            }
            else if (buttons == MessageBoxButton.YesNo)
            {
                dialog.YesButton.Content = "Yes";
                dialog.NoButton.Content = "No";
                dialog.YesButton.Click += (s, e) => { dialog.Result = MessageBoxResult.Yes; dialog.Close(); };
                dialog.NoButton.Click += (s, e) => { dialog.Result = MessageBoxResult.No; dialog.Close(); };
            }
            else if (buttons == MessageBoxButton.OKCancel)
            {
                dialog.YesButton.Content = "OK";
                dialog.NoButton.Content = "Cancel";
                dialog.YesButton.Click += (s, e) => { dialog.Result = MessageBoxResult.OK; dialog.Close(); };
                dialog.NoButton.Click += (s, e) => { dialog.Result = MessageBoxResult.Cancel; dialog.Close(); };
            }

            dialog.ShowDialog();
            return dialog.Result;
        }

        private void YesButton_Click(object sender, RoutedEventArgs e)
        {
            Result = MessageBoxResult.Yes;
            Close();
        }

        private void NoButton_Click(object sender, RoutedEventArgs e)
        {
            Result = MessageBoxResult.No;
            Close();
        }
    }
}
