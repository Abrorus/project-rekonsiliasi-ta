import joblib
from sklearn.svm import SVC
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, f1_score, classification_report

def load_data():
    X_train = joblib.load('../models/X_train.pkl')
    X_test = joblib.load('../models/X_test.pkl')
    y_train = joblib.load('../models/y_train.pkl')
    y_test = joblib.load('../models/y_test.pkl')
    return X_train, X_test, y_train, y_test

def evaluate(name, model, X_test, y_test):
    y_pred = model.predict(X_test)
    acc = accuracy_score(y_test, y_pred)
    f1_macro = f1_score(y_test, y_pred, average='macro')

    print(f"\n=== {name} ===")
    print(f"Accuracy   : {acc:.4f}")
    print(f"Macro F1   : {f1_macro:.4f}")
    print(classification_report(y_test, y_pred, zero_division=0))

    return {'model': name, 'accuracy': acc, 'macro_f1': f1_macro}

def main():
    X_train, X_test, y_train, y_test = load_data()

    results = []

        # Model 1: SVM dengan kernel RBF
    svm = SVC(kernel='rbf', C=1.0, gamma='scale', random_state=42)
    svm.fit(X_train, y_train)
    results.append(evaluate('SVM (RBF)', svm, X_test, y_test))
    joblib.dump(svm, '../models/model_svm.pkl')

    # Model 1b: SVM linear sebagai pembanding (teks sering cocok pakai kernel linear)
    svm_linear = SVC(kernel='linear', C=1.0, random_state=42)
    svm_linear.fit(X_train, y_train)
    results.append(evaluate('SVM (Linear)', svm_linear, X_test, y_test))

    # Model 2: Random Forest
    rf = RandomForestClassifier(n_estimators=100, max_depth=15, min_samples_split=5, random_state=42)
    rf.fit(X_train, y_train)
    results.append(evaluate('Random Forest', rf, X_test, y_test))
    joblib.dump(rf, '../models/model_rf.pkl')

    # Ringkasan perbandingan
    print("\n=== Ringkasan Perbandingan ===")
    for r in results:
        print(f"{r['model']:<20} Accuracy: {r['accuracy']:.4f}  Macro F1: {r['macro_f1']:.4f}")

if __name__ == '__main__':
    main()