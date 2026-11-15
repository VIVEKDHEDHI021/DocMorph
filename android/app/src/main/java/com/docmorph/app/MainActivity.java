package com.docmorph.app;

import android.os.Bundle;
import com.docmorph.app.plugin.DocMorphPlugin;
import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {
    @Override
    public void onCreate(Bundle savedInstanceState) {
        registerPlugin(DocMorphPlugin.class);
        super.onCreate(savedInstanceState);
    }
}
