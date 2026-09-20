# OpenDisplay USB ProGuard Rules

# Keep serialization classes
-keepattributes *Annotation*
-keepattributes Signature
-keepattributes Exceptions

# kotlinx.serialization
-keepclassmembers class kotlinx.serialization.json.** {
    *** Companion;
}
-keepclasseswithmembers class kotlinx.serialization.** {
    kotlinx.serialization.KSerializer serializer(...);
}
-keep,includedescriptorclasses class com.opendisplay.usb.**$$serializer { *; }
-keepclassmembers class com.opendisplay.usb.** {
    *** Companion;
}
-keepclasseswithmembers class com.opendisplay.usb.** {
    kotlinx.serialization.KSerializer serializer(...);
}
