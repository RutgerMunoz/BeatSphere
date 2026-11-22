package com.beatsphere.media;

import android.content.Context;
import android.net.Uri;

import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.OutputStream;

/**
 * Copies a picked content:// item (Google Photos, Drive, Gallery...) into a real file the app owns.
 * Done in Java because byte-array reads are awkward through pyjnius.
 */
public class UriFiles {
    public static boolean copy(Context context, Uri uri, String destination) {
        try (InputStream in = context.getContentResolver().openInputStream(uri);
             OutputStream out = new FileOutputStream(destination)) {
            if (in == null) {
                return false;
            }
            byte[] buffer = new byte[64 * 1024];
            int read;
            while ((read = in.read(buffer)) != -1) {
                out.write(buffer, 0, read);
            }
            return true;
        } catch (Exception e) {
            return false;
        }
    }
}
