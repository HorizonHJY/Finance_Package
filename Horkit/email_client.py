import win32com.client

def get_email_from_outlook(name):
    outlook = win32com.client.Dispatch("Outlook.Application")
    namespace = outlook.GetNamespace("MAPI")
    address_list = namespace.AddressLists.Item("Global Address List")  # 也可以试 "All Users"

    for entry in address_list.AddressEntries:
        if name.lower() in entry.Name.lower():
            return entry.GetExchangeUser().PrimarySmtpAddress
    return None

# 示例
names = ["John Smith", "Jane Doe"]
for name in names:
    print(name, "->", get_email_from_outlook(name))
