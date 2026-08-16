# Offline NuGet packages for Flutter Windows builds.
#
# Currently required:
#   Microsoft.Windows.CppWinRT.2.0.210806.1
#   (pulled by permission_handler_windows CMakeLists.txt)
#
# When api.nuget.org is unreachable, `frontend/nuget.config` points here so
# `nuget install` succeeds without the public feed.
#
# Refresh from a machine that already has the package cached:
#   copy %USERPROFILE%\.nuget\packages\microsoft.windows.cppwinrt\2.0.210806.1\*.nupkg .
